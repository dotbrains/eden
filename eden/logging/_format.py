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
    if event.type == "idle_warning":
        return f"{prefix} minutes_idle={event.minutes_idle}"
    if event.type == "tool_call":
        return f"{prefix} {event.tool_name} {event.tool_input}"
    if event.type == "usage":
        return f"{prefix} session_id={event.session_id} usage={event.usage}"
    if event.type == "session_id":
        return f"{prefix} session_id={event.session_id}"
    return prefix
