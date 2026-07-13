"""Agent stdin and stream parsing helpers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import cast

from eden.agents._context import IterationContext
from eden.agents._protocol import Agent
from eden.providers._protocols import SandboxHandle
from eden.streaming import StreamEvent


def stdin_payload(
    *,
    agent: Agent,
    iteration: int,
    rendered_prompt: str,
    handle: SandboxHandle,
    worktree_path: Path,
    branch: str,
    name: str | None,
    resume_session: str | None,
) -> str | None:
    stdin_fn = getattr(agent, "stdin_content", None)
    if not callable(stdin_fn):
        return None
    return cast(
        str | None,
        stdin_fn(
            IterationContext(
                iteration=iteration,
                prompt=rendered_prompt,
                sandbox_handle=handle,
                worktree_path=worktree_path,
                branch=branch,
                name=name,
                resume_session=resume_session,
            )
        ),
    )


def parse_event(
    *,
    agent: Agent,
    line: str,
    iteration: int,
    timestamp: Callable[[], datetime],
) -> StreamEvent:
    parsed = agent.parse_stream(line)
    if parsed is not None:
        return replace(parsed, iteration=iteration, agent_name=agent.name)
    return StreamEvent(
        type="text",
        agent_name=agent.name,
        iteration=iteration,
        timestamp=timestamp(),
        text=line,
    )


__all__ = ["parse_event", "stdin_payload"]
