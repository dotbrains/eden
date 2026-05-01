"""Idle watchdog — tracks last-activity, surfaces warnings + timeout from the main thread."""

from __future__ import annotations

import threading
import time
from queue import Empty, Queue

from eden.errors import IdleTimeout


class IdleWatchdog:
    """Polled watchdog. Caller calls record_activity() per stdout line.
    poll_warning() pops queued warnings; check_timeout() raises if the deadline
    has elapsed without activity."""

    def __init__(
        self,
        *,
        idle_timeout: float,
        idle_warning_interval: float | None,
    ) -> None:
        self._idle_timeout = idle_timeout
        self._warn_interval = idle_warning_interval
        self._last_activity = time.monotonic()
        self._activity_lock = threading.Lock()
        self._warnings: Queue[int] = Queue()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._warn_interval is None:
            return
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

    def record_activity(self) -> None:
        with self._activity_lock:
            self._last_activity = time.monotonic()

    def poll_warning(self) -> int | None:
        try:
            return self._warnings.get_nowait()
        except Empty:
            return None

    def check_timeout(self) -> None:
        with self._activity_lock:
            elapsed = time.monotonic() - self._last_activity
        if elapsed >= self._idle_timeout:
            raise IdleTimeout(
                message=(
                    f"agent produced no stdout for {elapsed:.1f}s "
                    f"(idle_timeout={self._idle_timeout}s)"
                ),
                hint="raise idle_timeout or check the agent's output",
            )

    def _loop(self) -> None:
        assert self._warn_interval is not None
        last_warn = time.monotonic()
        while not self._stop.is_set():
            self._stop.wait(timeout=self._warn_interval / 2)
            if self._stop.is_set():
                return
            now = time.monotonic()
            with self._activity_lock:
                idle_for = now - self._last_activity
            if idle_for >= self._warn_interval and (now - last_warn) >= self._warn_interval:
                self._warnings.put(int(idle_for // 60))
                last_warn = now
