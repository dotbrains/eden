"""Compatibility re-export for the shared streaming bounded-tail helper."""

from eden.streaming._bounded_tail import DEFAULT_MAX_CHARS, BoundedTail

__all__ = ["DEFAULT_MAX_CHARS", "BoundedTail"]
