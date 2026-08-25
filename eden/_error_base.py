"""Shared base and formatter for Eden error classes."""

from __future__ import annotations


class EdenError(Exception):
    """Base for every error raised from the eden package."""

    retryable: bool = False


def _format(code: str, message: str, hint: str | None) -> str:
    """Return ``[code] message`` with an optional newline-prefixed hint."""
    base = f"[{code}] {message}"
    return f"{base}\nhint: {hint}" if hint else base
