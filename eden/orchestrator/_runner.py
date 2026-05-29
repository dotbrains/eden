"""Agent process runner: spawn, stream stdout, integrate idle + abort."""

from __future__ import annotations

import os
import subprocess
import threading
import time
from collections.abc import Callable, Generator, Mapping
from dataclasses import dataclass
from pathlib import Path
from queue import Empty, Queue
from typing import IO, Any

from eden.abort import AbortSignal
from eden.orchestrator._idle import IdleWatchdog

_SENTINEL: Any = object()
_GRACE_SECONDS = 5.0


@dataclass(frozen=True)
class DrainResult:
    """Outcome of :meth:`_AgentRunner.drain_remaining`."""

    lines: list[str]
    """Trailing lines accumulated before the drain exited."""
    timed_out: bool
    """``True`` iff the drain exited because ``total_timeout`` elapsed."""


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
        stdin: str | None = None,
    ) -> None:
        self._argv = list(argv)
        self._env = dict(env)
        self._watchdog = watchdog
        self._cwd = cwd
        self._stdin = stdin
        self._proc: subprocess.Popen[str] | None = None
        self._stdout_q: Queue[Any] = Queue()
        self._stderr_chunks: list[str] = []

    def __enter__(self) -> _AgentRunner:
        merged = dict(os.environ)
        merged.update(self._env)
        # When stdin payload is provided, open a pipe so we can write to it; the
        # write is offloaded to a daemon thread so a large prompt cannot deadlock
        # against a slow-consuming agent (and doesn't block the main loop).
        stdin_pipe = subprocess.PIPE if self._stdin is not None else None
        self._proc = subprocess.Popen(
            self._argv,
            env=merged,
            cwd=str(self._cwd) if self._cwd is not None else None,
            stdin=stdin_pipe,
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
        if self._stdin is not None:
            stdin_stream = self._proc.stdin
            stdin_payload = self._stdin
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

    def drain_remaining(
        self,
        *,
        total_timeout: float | None = None,
        per_item_timeout: float = 0.5,
    ) -> DrainResult:
        """Return buffered lines remaining after the completion signal.

        Called once the completion signal is matched so trailing lines
        (e.g. the ``result`` JSON emitted by ``claude --output-format
        stream-json``) are captured before the process is terminated.

        Three exit conditions:

        * **EOF** — sentinel arrives → process has cleanly closed stdout.
        * **idle** — no line for ``per_item_timeout`` seconds → drain
          considered complete; process may still be running.
        * **timeout** — total wall time ``total_timeout`` elapses → drain
          aborted because the agent emitted the completion signal but a
          child process kept the stdout pipe open. Mirrors sandcastle's
          ``completionTimeoutSeconds`` (v0.6.6, ddc26ba).

        ``total_timeout=None`` disables the bounded budget — only EOF or
        idle exit the loop (the pre-v0.6.6 behaviour).
        """
        deadline = time.monotonic() + total_timeout if total_timeout is not None else None
        lines: list[str] = []
        timed_out = False
        while True:
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    timed_out = True
                    break
                wait = min(per_item_timeout, remaining)
            else:
                wait = per_item_timeout
            try:
                item = self._stdout_q.get(timeout=wait)
            except Empty:
                # ``Empty`` is ambiguous when the wait was clamped by the
                # deadline: the queue may have had items pending but the
                # clamped window expired first. Re-check the deadline so
                # a noisy-child scenario reports ``timed_out=True`` rather
                # than a false "idle" exit.
                if deadline is not None and time.monotonic() >= deadline:
                    timed_out = True
                break
            if item is _SENTINEL:
                break
            lines.append(item.rstrip("\n"))
        return DrainResult(lines=lines, timed_out=timed_out)

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

    def exit_code(self, *, wait_timeout: float = _GRACE_SECONDS) -> int | None:
        """Return the agent process's exit code, or ``None`` if still running.

        Called after ``iter_lines`` returns naturally (queue sentinel reached
        on EOF) so the caller can distinguish a clean ``0`` from a non-zero
        exit before deciding whether to raise ``AgentError``.
        """
        proc = self._proc
        if proc is None:
            return None
        rc = proc.poll()
        if rc is not None:
            return rc
        try:
            return proc.wait(timeout=wait_timeout)
        except subprocess.TimeoutExpired:
            return None

    @property
    def stderr_text(self) -> str:
        """Return the captured stderr accumulated so far. Safe after EOF."""
        return "".join(self._stderr_chunks)
