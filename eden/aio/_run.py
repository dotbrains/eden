"""Async wrapper for :func:`eden.run`."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from datetime import timedelta
from pathlib import Path

from eden import (
    AbortSignal,
    Agent,
    BranchStrategy,
    Hooks,
    Logging,
    OutputDefinition,
    RunResult,
    StreamEvent,
    Timeouts,
)
from eden.orchestrator import run as _sync_run
from eden.providers._protocols import SandboxProvider


async def run(
    *,
    agent: Agent,
    sandbox: SandboxProvider,
    prompt: str | None = None,
    prompt_file: str | Path | None = None,
    prompt_args: Mapping[str, object] | None = None,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    branch_strategy: BranchStrategy | None = None,
    base_branch: str | None = None,
    max_iterations: int = 1,
    completion_signal: str | list[str] = "<promise>COMPLETE</promise>",
    idle_timeout: float | timedelta = 600.0,
    idle_warning_interval: float | timedelta | None = None,
    completion_timeout: float | timedelta | None = 60.0,
    name: str | None = None,
    hooks: Hooks | None = None,
    timeouts: Timeouts | None = None,
    on_event: Callable[[StreamEvent], None] | None = None,
    logging: Logging | None = None,
    signal: AbortSignal | None = None,
    output: OutputDefinition | None = None,
    resume_session: str | None = None,
    fork_session: bool = False,
    copy_to_worktree: list[str] | None = None,
    throw_on_duplicate_worktree: bool = True,
) -> RunResult:
    """Async wrapper around :func:`eden.run`."""
    return await asyncio.to_thread(
        _sync_run,
        agent=agent,
        sandbox=sandbox,
        prompt=prompt,
        prompt_file=prompt_file,
        prompt_args=prompt_args,
        cwd=cwd,
        env=env,
        branch_strategy=branch_strategy,
        base_branch=base_branch,
        max_iterations=max_iterations,
        completion_signal=completion_signal,
        idle_timeout=idle_timeout,
        idle_warning_interval=idle_warning_interval,
        completion_timeout=completion_timeout,
        name=name,
        hooks=hooks,
        timeouts=timeouts,
        on_event=on_event,
        logging=logging,
        signal=signal,
        output=output,
        resume_session=resume_session,
        fork_session=fork_session,
        copy_to_worktree=copy_to_worktree,
        throw_on_duplicate_worktree=throw_on_duplicate_worktree,
    )
