from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime

from eden.agents._protocol import Agent
from eden.orchestrator._logging import LoopLogger
from eden.orchestrator._runner import _AgentRunner
from eden.streaming import StreamEvent
from eden.streaming._bounded_tail import BoundedTail


def drain_after_completion(
    *,
    runner: _AgentRunner,
    agent: Agent,
    iteration: int,
    completion_timeout: float | None,
    logger: LoopLogger,
    on_event: Callable[[StreamEvent], None] | None,
    stdout_chunks: BoundedTail,
    timestamp: Callable[[], datetime],
    emit_raw: Callable[[str], None],
    handle_event: Callable[[StreamEvent], None],
) -> None:
    drain = runner.drain_remaining(total_timeout=completion_timeout)
    if drain.timed_out:
        warn_ev = StreamEvent(
            type="text",
            agent_name=agent.name,
            iteration=iteration,
            timestamp=timestamp(),
            text=(
                f"[eden] completion_timeout ({completion_timeout}s) "
                "elapsed after completion signal — agent process did "
                "not EOF; terminating now. Iteration succeeded."
            ),
        )
        logger.write(warn_ev)
        if on_event is not None:
            on_event(warn_ev)
    for trailing in drain.lines:
        stdout_chunks.push(trailing + "\n")
        emit_raw(trailing)
        trailing_parsed = agent.parse_stream(trailing)
        if trailing_parsed is not None:
            handle_event(
                replace(
                    trailing_parsed,
                    iteration=iteration,
                    agent_name=agent.name,
                )
            )


__all__ = ["drain_after_completion"]
