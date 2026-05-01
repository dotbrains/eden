"""Completion-signal substring matcher."""

from __future__ import annotations


def match(line: str, signal: str | list[str]) -> str | None:
    """Return the first matching signal substring, or None."""
    if isinstance(signal, str):
        return signal if signal in line else None
    for needle in signal:
        if needle and needle in line:
            return needle
    return None
