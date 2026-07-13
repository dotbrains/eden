"""Session storage and tracing setup for orchestrator loop runs."""

from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass

from opentelemetry import trace

from eden.agents._protocol import Agent
from eden.orchestrator._session_capture import resolve_session_storage
from eden.orchestrator.loop._run_span import enter_run_span
from eden.providers._protocols import SandboxProvider
from eden.providers._types import Mount
from eden.session._protocol import SessionStorage
from eden.worktree._create import WorktreeHandle


@dataclass(frozen=True)
class LoopSessionContext:
    storage: SessionStorage | None
    extra_mounts: tuple[Mount, ...]
    stack: ExitStack
    run_span: trace.Span


def prepare_loop_session_context(
    *,
    agent: Agent,
    sandbox: SandboxProvider,
    worktree: WorktreeHandle,
    max_iterations: int,
    caller_managed: bool,
) -> LoopSessionContext:
    storage = resolve_session_storage(agent)
    stack = ExitStack()
    run_span = enter_run_span(
        stack,
        agent=agent,
        sandbox=sandbox,
        worktree=worktree,
        max_iterations=max_iterations,
        caller_managed=caller_managed,
    )
    return LoopSessionContext(
        storage=storage,
        extra_mounts=storage.extra_mounts() if storage else (),
        stack=stack,
        run_span=run_span,
    )


__all__ = ["LoopSessionContext", "prepare_loop_session_context"]
