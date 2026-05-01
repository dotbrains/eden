"""Format StreamEvents into newline-delimited log lines."""

from __future__ import annotations

from typing import Literal

from eden.streaming import StreamEvent


def format_line(
    event: StreamEvent,
    *,
    level: Literal["debug", "info", "warn", "error"],
) -> str:
    iso = event.timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
    prefix = f"{iso} {level} [{event.iteration}] {event.type}:"
    if event.type == "text":
        body = (event.text or "").rstrip("\n")
        return f"{prefix} {body}"
    return f"{prefix} minutes_idle={event.minutes_idle}"
