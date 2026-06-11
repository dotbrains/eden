"""Stdout-sink writer — same formatting/redaction as the file sink."""

from __future__ import annotations

import sys
import threading
from collections.abc import Iterable
from typing import Literal

from eden.logging._format import format_line
from eden.logging._redact import redact
from eden.streaming import StreamEvent


class StdoutLogSink:
    """Plain-text log sink targeting ``sys.stdout``. Redaction applied on every write.

    Thread-safe: ``write`` and ``close`` are serialized by an internal lock.
    ``close`` only flushes — stdout belongs to the host process and stays
    open. ``sys.stdout`` is resolved per write so test harnesses that swap it
    (pytest's ``capsys``) observe the output.
    """

    def __init__(
        self,
        *,
        level: Literal["debug", "info", "warn", "error"],
        env_values: Iterable[str],
    ) -> None:
        self.level = level
        self._env_values = tuple(env_values)
        self._lock = threading.Lock()
        self._closed = False

    def write(self, event: StreamEvent) -> None:
        with self._lock:
            if self._closed:
                return
            line = format_line(event, level=self.level)
            line = redact(line, env_values=self._env_values)
            sys.stdout.write(line + "\n")
            sys.stdout.flush()

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            try:
                sys.stdout.flush()
            except ValueError:
                # Host already closed its stdout (interpreter teardown).
                pass
