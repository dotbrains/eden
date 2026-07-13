"""Shared helpers for eden init CLI tests."""

from __future__ import annotations

import re

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def strip_ansi(text: str) -> str:
    """Drop ANSI color codes so substring asserts survive rich styling."""
    return _ANSI_RE.sub("", text)
