"""Event helpers for loop iterations."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from eden._types import Usage
from eden.orchestrator._logging import LoopLogger
from eden.orchestrator._summary import format_context_window_line
from eden.streaming import StreamEvent


def _utcnow() -> datetime:
    return datetime.now(UTC)


def emit_context_window(
    *,
    agent_name: str,
    iteration: int,
    usage: Usage | None,
    logger: LoopLogger,
    on_event: Callable[[StreamEvent], None] | None,
) -> None:
    if usage is None:
        return
    ctx_ev = StreamEvent(
        type="text",
        agent_name=agent_name,
        iteration=iteration,
        timestamp=_utcnow(),
        text=format_context_window_line(usage),
    )
    logger.write(ctx_ev)
    if on_event is not None:
        on_event(ctx_ev)


__all__ = ["emit_context_window"]
