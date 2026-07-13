"""Tracing span helpers for orchestrator runs."""

from __future__ import annotations

from contextlib import ExitStack

from opentelemetry import trace

from eden.agents._protocol import Agent
from eden.providers._protocols import SandboxProvider
from eden.tracing import span
from eden.worktree._create import WorktreeHandle


def enter_run_span(
    stack: ExitStack,
    *,
    agent: Agent,
    sandbox: SandboxProvider,
    worktree: WorktreeHandle,
    max_iterations: int,
    caller_managed: bool,
) -> trace.Span:
    """Enter the outer ``eden.run`` span on ``stack``."""
    return stack.enter_context(
        span(
            "eden.run",
            attributes={
                "agent.name": agent.name,
                "agent.model": getattr(agent, "model", None),
                "sandbox.name": sandbox.name,
                "sandbox.kind": sandbox.kind,
                "branch": worktree.branch,
                "max_iterations": max_iterations,
                "caller_managed": caller_managed,
            },
        )
    )


__all__ = ["enter_run_span"]
