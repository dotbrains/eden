"""Streaming subprocess helper used by no_sandbox and docker handles."""

from __future__ import annotations

import os
import subprocess
import threading
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from queue import Empty, Queue
from typing import IO, Any

from eden.providers._types import ExecResult
from eden.sandboxes.errors import ExecTimeout

_SENTINEL: Any = object()


def _drain(stream: IO[str], queue: Queue[Any]) -> None:
    try:
        for line in iter(stream.readline, ""):
            queue.put(line)
    finally:
        queue.put(_SENTINEL)


def stream_exec(
    argv: list[str] | str,
    *,
    cmd_for_error: str,
    shell: bool = False,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    on_line: Callable[[str], None] | None = None,
    timeout: float | None = None,
    stdin: str | None = None,
) -> ExecResult:
    """Run a subprocess with line-buffered stdout+stderr drained via threads.

    On `timeout`: SIGTERM, then SIGKILL after a 5s grace, then raise
    `ExecTimeout` carrying whatever was captured.

    ``stdin``, when given, is written to the process's stdin on a daemon
    thread. The write is offloaded so a large payload can't deadlock
    against a slow-consuming child (the parent stays in the drain loop).
    """
    merged_env: dict[str, str] = dict(os.environ)
    if env:
        merged_env.update(env)

    proc = subprocess.Popen(
        argv,
        shell=shell,
        cwd=str(cwd) if cwd is not None else None,
        env=merged_env,
        stdin=subprocess.PIPE if stdin is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    assert proc.stdout is not None
    assert proc.stderr is not None

    if stdin is not None:
        stdin_stream = proc.stdin
        stdin_payload = stdin
        assert stdin_stream is not None

        def _write_stdin() -> None:
            try:
                stdin_stream.write(stdin_payload)
            finally:
                try:
                    stdin_stream.close()
                except Exception:
                    pass

        threading.Thread(target=_write_stdin, daemon=True).start()

    stdout_q: Queue[Any] = Queue()
    stderr_q: Queue[Any] = Queue()
    t_out = threading.Thread(target=_drain, args=(proc.stdout, stdout_q), daemon=True)
    t_err = threading.Thread(target=_drain, args=(proc.stderr, stderr_q), daemon=True)
    t_out.start()
    t_err.start()

    out_chunks: list[str] = []
    err_chunks: list[str] = []
    out_done = False
    err_done = False
    deadline = (time.monotonic() + timeout) if timeout is not None else None

    while not (out_done and err_done):
        if deadline is not None and time.monotonic() > deadline:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            raise ExecTimeout(
                cmd=cmd_for_error,
                timeout=timeout or 0.0,
                partial_stdout="".join(out_chunks),
                partial_stderr="".join(err_chunks),
            )

        if not out_done:
            try:
                item = stdout_q.get(timeout=0.05)
            except Empty:
                item = None
            if item is _SENTINEL:
                out_done = True
            elif item is not None:
                out_chunks.append(item)
                if on_line is not None:
                    on_line(item.rstrip("\n"))

        if not err_done:
            try:
                item = stderr_q.get(timeout=0.05)
            except Empty:
                item = None
            if item is _SENTINEL:
                err_done = True
            elif item is not None:
                err_chunks.append(item)
                if on_line is not None:
                    on_line(item.rstrip("\n"))

    proc.wait()
    return ExecResult(
        stdout="".join(out_chunks),
        stderr="".join(err_chunks),
        exit_code=proc.returncode,
    )
