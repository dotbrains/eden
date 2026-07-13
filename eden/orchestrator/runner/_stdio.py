"""Stdout and stdin helpers for the agent process runner."""

from __future__ import annotations

from dataclasses import dataclass
from queue import Queue
from typing import IO, Any

SENTINEL: Any = object()


@dataclass(frozen=True)
class DrainResult:
    """Outcome of :meth:`_AgentRunner.drain_remaining`."""

    lines: list[str]
    """Trailing lines accumulated before the drain exited."""
    timed_out: bool
    """``True`` iff the drain exited because ``total_timeout`` elapsed."""


def drain_stream(stream: IO[str], queue: Queue[Any]) -> None:
    try:
        for line in iter(stream.readline, ""):
            queue.put(line)
    finally:
        queue.put(SENTINEL)


def write_and_close(stream: IO[str], payload: str) -> None:
    try:
        stream.write(payload)
    finally:
        try:
            stream.close()
        except Exception:
            pass
