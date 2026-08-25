"""Stream-to-queue drain helper for LocalProcess."""

from __future__ import annotations

from queue import Queue
from typing import IO, Any

_SENTINEL: Any = object()


def drain_stream(stream: IO[str], queue: Queue[Any]) -> None:
    try:
        for line in iter(stream.readline, ""):
            queue.put(line)
    finally:
        queue.put(_SENTINEL)


__all__ = ["_SENTINEL", "drain_stream"]
