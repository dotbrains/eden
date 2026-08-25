"""Non-blocking local subprocess handle shared by bind-mount providers."""

from __future__ import annotations

import os
import subprocess
import threading
import time
from collections.abc import Iterator, Mapping
from pathlib import Path
from queue import Empty, Queue
from typing import Any

from eden.providers._process_local_support import _SENTINEL, drain_stream
from eden.providers._types import ExecResult, ProcessStatus


class LocalProcess:
    def __init__(self, proc: subprocess.Popen[str], cmd: str) -> None:
        self._proc = proc
        self._cmd = cmd
        self._stdout_q: Queue[Any] = Queue()
        self._stderr_q: Queue[Any] = Queue()
        assert proc.stdout is not None and proc.stderr is not None
        threading.Thread(
            target=drain_stream, args=(proc.stdout, self._stdout_q), daemon=True,
        ).start()
        threading.Thread(
            target=drain_stream, args=(proc.stderr, self._stderr_q), daemon=True,
        ).start()
        self._stdout_lines: list[str] = []
        self._stderr_parts: list[str] = []
        self._stdout_done = False
        self._stderr_done = False
        self._killed = False

    def status(self) -> ProcessStatus:
        code = self._proc.poll()
        if code is None:
            return ProcessStatus(state="running", exit_code=None)
        if self._killed:
            return ProcessStatus(state="killed", exit_code=code)
        return ProcessStatus(
            state="exited" if code == 0 else "failed",
            exit_code=0 if code == 0 else code,
        )

    def output(self) -> Iterator[str]:
        while not self._stdout_done:
            try:
                item = self._stdout_q.get(timeout=0.05)
            except Empty:
                if self._proc.poll() is not None and self._stdout_q.empty():
                    self._stdout_done = True
                    break
                continue
            if item is _SENTINEL:
                self._stdout_done = True
            else:
                line = str(item).rstrip("\n")
                self._stdout_lines.append(line)
                yield line
        self._pump_stderr_once()

    def write(self, data: str) -> None:
        stdin = self._proc.stdin
        if stdin is None:
            return
        stdin.write(data)
        stdin.flush()

    def wait(self, *, timeout: float | None = None) -> ExecResult:
        from eden.sandboxes.errors import ExecTimeout

        deadline = (time.monotonic() + timeout) if timeout is not None else None
        try:
            if deadline is not None:
                self._proc.wait(timeout=max(0.0, deadline - time.monotonic()))
            else:
                self._proc.wait()
        except subprocess.TimeoutExpired:
            self.kill()
            raise ExecTimeout(
                cmd=self._cmd,
                timeout=timeout or 0.0,
                partial_stdout="\n".join(self._stdout_lines),
                partial_stderr="".join(self._stderr_parts),
            ) from None
        self._pump_remaining()
        stdout = "\n".join(self._stdout_lines)
        if stdout and not stdout.endswith("\n"):
            stdout += "\n"
        return ExecResult(
            stdout=stdout,
            stderr="".join(self._stderr_parts),
            exit_code=self._proc.returncode or 0,
        )

    def kill(self) -> None:
        self._killed = True
        if self._proc.poll() is None:
            self._proc.kill()
            self._proc.wait()

    def _pump_stderr_once(self) -> None:
        if self._stderr_done:
            return
        while True:
            try:
                item = self._stderr_q.get_nowait()
            except Empty:
                return
            if item is _SENTINEL:
                self._stderr_done = True
                return
            self._stderr_parts.append(str(item))

    def _pump_remaining(self) -> None:
        while not self._stdout_done:
            try:
                item = self._stdout_q.get(timeout=0.05)
            except Empty:
                if self._proc.poll() is not None:
                    self._stdout_done = True
                    break
                continue
            if item is _SENTINEL:
                self._stdout_done = True
            else:
                self._stdout_lines.append(str(item).rstrip("\n"))
        while not self._stderr_done:
            try:
                item = self._stderr_q.get(timeout=0.05)
            except Empty:
                if self._proc.poll() is not None:
                    self._stderr_done = True
                    break
                continue
            if item is _SENTINEL:
                self._stderr_done = True
            else:
                self._stderr_parts.append(str(item))


def start_local_process(
    argv: list[str] | str,
    *,
    cmd_for_error: str,
    shell: bool = False,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> LocalProcess:
    merged_env = dict(os.environ)
    if env:
        merged_env.update(env)
    proc = subprocess.Popen(
        argv,
        shell=shell,
        cwd=str(cwd) if cwd is not None else None,
        env=merged_env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    return LocalProcess(proc, cmd=cmd_for_error)
