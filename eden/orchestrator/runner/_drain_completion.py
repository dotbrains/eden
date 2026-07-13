"""Drain buffered stdout after an agent emits the completion signal."""

from __future__ import annotations

import time
from queue import Empty, Queue
from typing import Any

from eden.orchestrator.runner._stdio import SENTINEL, DrainResult


def drain_completion(
    stdout_q: Queue[Any],
    *,
    total_timeout: float | None,
    per_item_timeout: float,
) -> DrainResult:
    deadline = time.monotonic() + total_timeout if total_timeout is not None else None
    lines: list[str] = []
    timed_out = False
    while True:
        if deadline is not None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                break
            wait = min(per_item_timeout, remaining)
        else:
            wait = per_item_timeout
        try:
            item = stdout_q.get(timeout=wait)
        except Empty:
            if deadline is not None and time.monotonic() >= deadline:
                timed_out = True
            break
        if item is SENTINEL:
            break
        lines.append(item.rstrip("\n"))
    return DrainResult(lines=lines, timed_out=timed_out)


__all__ = ["drain_completion"]
