"""AbortSignal — threading.Event-backed cooperative cancellation."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

from eden.errors import Aborted


@dataclass
class AbortSignal:
    """Read-only-ish view: callers can check / wait / raise, but cannot trigger."""

    _event: threading.Event = field(default_factory=threading.Event)
    # list-of-one avoids dataclass mutable-default restriction; index 0 is the reason
    _reason: list[str | None] = field(default_factory=lambda: [None])
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def is_aborted(self) -> bool:
        return self._event.is_set()

    @property
    def reason(self) -> str | None:
        """Cancellation reason. ``None`` until ``abort()`` is called."""
        return self._reason[0]

    def raise_if_aborted(self) -> None:
        if self._event.is_set():
            raise Aborted(reason=self._reason[0] or "abort-signal")

    def wait(self, timeout: float | None = None) -> bool:
        return self._event.wait(timeout)


@dataclass
class AbortController:
    """Writer side of an AbortSignal."""

    signal: AbortSignal = field(default_factory=AbortSignal)

    def abort(self, *, reason: str = "abort-signal") -> None:
        with self.signal._lock:
            if not self.signal._event.is_set():
                self.signal._reason[0] = reason
                self.signal._event.set()
