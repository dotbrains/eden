"""Duration conversion helpers for sandbox APIs."""

from __future__ import annotations

from datetime import timedelta


def seconds(value: float | timedelta) -> float:
    if isinstance(value, timedelta):
        return value.total_seconds()
    return float(value)


def maybe_seconds(value: float | timedelta | None) -> float | None:
    if value is None:
        return None
    return seconds(value)
