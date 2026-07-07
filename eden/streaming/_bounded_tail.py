"""Fixed-size rolling tail for streamed output."""

from __future__ import annotations

DEFAULT_MAX_CHARS = 64 * 1024
"""Default tail budget (64 KiB)."""


class BoundedTail:
    """Fixed-size rolling tail of pushed strings, bounded by total length.

    ``push`` appends; once the joined length would exceed ``max_chars``,
    the oldest items are dropped from the front. A single item larger
    than ``max_chars`` is truncated to its own tail before it lands, so
    a newline-free blob can't overflow on one push. ``to_string`` joins
    the retained items; its length is always at most ``max_chars``.
    """

    def __init__(
        self,
        max_chars: int = DEFAULT_MAX_CHARS,
        *,
        separator: str = "",
    ) -> None:
        if max_chars < 1:
            raise ValueError(f"max_chars must be >= 1; got {max_chars}")
        self._items: list[str] = []
        self._total = 0
        self._max = max_chars
        self._sep = separator

    def push(self, item: str) -> None:
        """Append ``item`` to the tail, evicting oldest entries to stay in budget."""
        if not item:
            return
        bounded = item[-self._max :] if len(item) > self._max else item
        sep_cost = len(self._sep) if self._items else 0
        self._items.append(bounded)
        self._total += len(bounded) + sep_cost
        while self._total > self._max and len(self._items) > 1:
            dropped = self._items.pop(0)
            self._total -= len(dropped) + len(self._sep)

    def to_string(self) -> str:
        """Join the retained tail. Length is always <= ``max_chars``."""
        return self._sep.join(self._items)

    def __len__(self) -> int:
        return self._total


__all__ = ["DEFAULT_MAX_CHARS", "BoundedTail"]
