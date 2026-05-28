"""Fixed-size rolling tail for streamed agent output.

The orchestrator accumulates every line of agent stdout into a buffer
so the run's final result can carry ``stdout``, ``parse_stdout_error``
can find the agent's tail-of-stream error block, and
``Output.object`` can scan for the agent's structured-output tag. An
unbounded list grows linearly with run length; multi-hour runs on
chatty agents can drive memory into the hundreds of megabytes before
the loop terminates.

A rolling tail caps memory in exchange for losing the *head* of the
stream. That trade is sound for Eden's three consumers — all of them
care about the last lines the agent emitted, not the first:

* ``parse_stdout_error`` extracts the agent's final error block, which
  the agent emits just before exiting non-zero.
* ``Output.object`` / ``Output.string`` find a ``<tag>...</tag>``
  payload that the prompt instructs the agent to emit at the end.
* The completion signal match runs line-by-line as it streams, so
  bounding the buffer can't lose a hit that has already fired.

Mirrors sandcastle's ``boundedTail.ts``. The V8-specific failure mode
(``RangeError: Invalid string length`` past ~512 MB) doesn't apply to
CPython, but the underlying "unbounded accumulation on long runs" hazard
does.
"""

from __future__ import annotations

DEFAULT_MAX_CHARS = 64 * 1024
"""Default tail budget (64 KiB).

Sits comfortably above every completion signal and structured-output
payload Eden has shipped while staying small enough that even a
runaway agent loop keeps the buffer in cache.
"""


class BoundedTail:
    """Fixed-size rolling tail of pushed strings, bounded by total length.

    ``push`` appends; once the joined length would exceed ``max_chars``,
    the oldest items are dropped from the front. A single item larger
    than ``max_chars`` is truncated to its own tail before it lands, so
    a newline-free blob can't overflow on one push. ``to_string`` joins
    the retained items; its length is always at most ``max_chars``.

    The running length counter is encapsulated so callers can't desync
    it from the underlying list.
    """

    def __init__(
        self,
        max_chars: int = DEFAULT_MAX_CHARS,
        *,
        separator: str = "",
    ) -> None:
        """Construct a fresh, empty tail.

        ``separator`` is placed between items by :meth:`to_string` and
        must match how the caller would otherwise have joined the
        accumulated chunks. Eden appends already-terminated lines, so
        the default ``""`` is correct; pass ``"\\n"`` for raw line
        streams that don't pre-terminate.
        """
        if max_chars < 1:
            raise ValueError(f"max_chars must be ≥ 1; got {max_chars}")
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
        """Join the retained tail. Length is always ≤ ``max_chars``."""
        return self._sep.join(self._items)

    def __len__(self) -> int:
        """Total character count currently retained."""
        return self._total


__all__ = ["DEFAULT_MAX_CHARS", "BoundedTail"]
