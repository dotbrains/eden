"""Run-summary helpers — formatters for stream-event lines emitted by the loop."""

from __future__ import annotations

from eden._types import Usage


def context_window_k(usage: Usage) -> int:
    """Return the context-window size in thousands of tokens, rounded up.

    Sums input + cache-creation + cache-read tokens (matching the formula used
    by upstream's run summary) and rounds up to the nearest 1000.
    """
    total = (
        usage.input_tokens
        + usage.cache_creation_input_tokens
        + usage.cache_read_input_tokens
    )
    return -(-total // 1000)


def format_context_window_line(usage: Usage) -> str:
    """Return ``"Context window: NNNk"`` for a usage record."""
    return f"Context window: {context_window_k(usage)}k"
