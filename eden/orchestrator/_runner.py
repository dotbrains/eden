"""Agent process runner: spawn, stream stdout, integrate idle + abort."""

from __future__ import annotations

import os
import subprocess
import threading
from collections.abc import Callable, Generator, Mapping
from pathlib import Path
from queue import Empty, Queue
from typing import IO, Any

from eden.abort import AbortSignal
from eden.orchestrator._idle import IdleWatchdog

_SENTINEL: Any = object()
_GRACE_SECONDS = 5.0


def _drain(stream: IO[str], queue: Queue[Any]) -> None:
    try:
        for line in iter(stream.readline, ""):
            queue.put(line)
    finally:
        queue.put(_SENTINEL)


class _AgentRunner:
    def __init__(
        self,
        *,
        argv: list[str],
        env: Mapping[str, str],
        watchdog: IdleWatchdog,
        cwd: Path | None = None,
    ) -> None:
        self._argv = list(argv)
        self._env = dict(env)
        self._watchdog = watchdog
        self._cwd = cwd
        self._proc: subprocess.Popen[str] | None = None
        self._stdout_q: Queue[Any] = Queue()
        self._stderr_chunks: list[str] = []

    def __enter__(self) -> _AgentRunner:
        merged = dict(os.environ)
        merged.update(self._env)
        self._proc = subprocess.Popen(
            self._argv,
            env=merged,
            cwd=str(self._cwd) if self._cwd is not None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        assert self._proc.stdout is not None
        assert self._proc.stderr is not None
        # Capture locals so the daemon lambdas don't go through self._proc (which
        # mypy cannot narrow after the assert inside a closure).
        stdout = self._proc.stdout
        stderr = self._proc.stderr
        threading.Thread(target=_drain, args=(stdout, self._stdout_q), daemon=True).start()
        # stderr is captured silently (logged at iteration end if non-empty).
        threading.Thread(
            target=lambda: self._stderr_chunks.extend(stderr),
            daemon=True,
        ).start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.terminate()

    def iter_lines(
        self,
        *,
        signal: AbortSignal,
        on_warning: Callable[[int], None],
    ) -> Generator[str, None, None]:
        assert self._proc is not None
        while True:
            signal.raise_if_aborted()
            warning = self._watchdog.poll_warning()
            if warning is not None:
                on_warning(warning)
            try:
                item = self._stdout_q.get(timeout=0.1)
            except Empty:
                self._watchdog.check_timeout()
                continue
            if item is _SENTINEL:
                return
            self._watchdog.record_activity()
            yield item.rstrip("\n")

    def drain_remaining(self, *, per_item_timeout: float = 0.5) -> list[str]:
        """Return buffered lines remaining after the completion signal.

        Called once the completion signal is matched so that trailing lines
        (e.g. the ``result`` JSON emitted by ``claude --output-format
        stream-json``) are captured before the process is terminated.  Each
        ``get`` waits up to *per_item_timeout* seconds; the loop exits as soon
        as the queue is empty for that window or a sentinel (EOF) arrives.
        """
        lines: list[str] = []
        while True:
            try:
                item = self._stdout_q.get(timeout=per_item_timeout)
            except Empty:
                break
            if item is _SENTINEL:
                break
            lines.append(item.rstrip("\n"))
        return lines

    def terminate(self) -> None:
        proc = self._proc
        if proc is None or proc.poll() is not None:
            self._proc = None
            return
        proc.terminate()
        try:
            proc.wait(timeout=_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        self._proc = None
