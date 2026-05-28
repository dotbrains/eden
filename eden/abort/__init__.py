"""Cooperative cancellation primitives."""

from __future__ import annotations

from eden.abort._shutdown import ShutdownCallback, register_shutdown
from eden.abort._signal import AbortController, AbortSignal
from eden.errors import Aborted

__all__ = [
    "AbortController",
    "AbortSignal",
    "Aborted",
    "ShutdownCallback",
    "register_shutdown",
]
