"""Run-summary helpers — formatters for stream-event lines emitted by the loop."""

from __future__ import annotations

from eden._types import Usage
from eden.providers._types import FinalizeResult


def context_window_k(usage: Usage) -> int:
    """Return the context-window size in thousands of tokens, rounded up.

    Sums input + cache-creation + cache-read tokens (matching the formula used
    by upstream's run summary) and rounds up to the nearest 1000.
    """
    total = usage.input_tokens + usage.cache_creation_input_tokens + usage.cache_read_input_tokens
    return -(-total // 1000)


def format_context_window_line(usage: Usage) -> str:
    """Return ``"Context window: NNNk"`` for a usage record."""
    return f"Context window: {context_window_k(usage)}k"


def format_finalize_line(result: FinalizeResult) -> str:
    """Return a human-readable summary of an isolated-sandbox finalize.

    ``"[eden] no changes to sync"`` when nothing changed,
    ``"[eden] syncing N file(s) to host (M bytes)"`` when changes applied,
    ``"[eden] sync incomplete: N file(s) attempted (M bytes)"`` when one or
    more file copies failed during apply. Mirrors upstream's commit-aware
    sync wording while keeping Eden's file-level granularity (Eden's isolated
    provider works at the file level, not the commit level).
    """
    n = len(result.files_changed)
    if n == 0:
        return "[eden] no changes to sync"
    suffix = "file" if n == 1 else "files"
    if not result.applied:
        return f"[eden] sync incomplete: {n} {suffix} attempted ({result.patch_size_bytes} bytes)"
    return f"[eden] syncing {n} {suffix} to host ({result.patch_size_bytes} bytes)"
