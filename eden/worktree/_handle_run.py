"""Run and sandbox helpers for ``WorktreeHandle``."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from eden._types import RunResult, Timeouts
from eden.abort import AbortSignal
from eden.lifecycle import Hooks
from eden.logging import Logging
from eden.output import OutputDefinition
from eden.providers._protocols import SandboxProvider
from eden.providers._types import Mount
from eden.streaming import StreamEvent

if TYPE_CHECKING:
    from eden.agents._protocol import Agent
    from eden.orchestrator.interactive import InteractiveResult
    from eden.sandboxes._sandbox import Sandbox
    from eden.worktree._handle import WorktreeHandle


def create_worktree_sandbox(
    worktree: WorktreeHandle,
    *,
    sandbox: SandboxProvider,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    mounts: tuple[Mount, ...] | None = None,
    name: str | None = None,
    hooks: Hooks | None = None,
    copy_to_worktree: list[str] | None = None,
    timeouts: Timeouts | None = None,
) -> Sandbox:
    """Create a sandbox backed by ``worktree`` without transferring ownership."""
    from eden.sandboxes import create_sandbox

    return create_sandbox(
        sandbox=sandbox,
        worktree=worktree,
        cwd=cwd,
        env=env,
        mounts=mounts,
        name=name,
        hooks=hooks,
        copy_to_worktree=copy_to_worktree,
        timeouts=timeouts,
    )


def run_in_worktree(
    worktree: WorktreeHandle,
    *,
    agent: Agent,
    sandbox: SandboxProvider,
    prompt: str | None = None,
    prompt_file: str | Path | None = None,
    prompt_args: Mapping[str, str] | None = None,
    env: Mapping[str, str] | None = None,
    mounts: tuple[Mount, ...] | None = None,
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
) -> RunResult:
    """Run an agent in a short-lived sandbox backed by ``worktree``."""
    with create_worktree_sandbox(
        worktree,
        sandbox=sandbox,
        env=env,
        mounts=mounts,
        name=name,
        hooks=hooks,
        copy_to_worktree=copy_to_worktree,
        timeouts=timeouts,
    ) as sb:
        return sb.run(
            agent=agent,
            prompt=prompt,
            prompt_file=prompt_file,
            prompt_args=prompt_args,
            env=env,
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
        )


def interactive_in_worktree(
    worktree: WorktreeHandle,
    *,
    agent: Agent,
    sandbox: SandboxProvider | None = None,
    prompt: str | None = None,
    prompt_file: str | Path | None = None,
    prompt_args: Mapping[str, str] | None = None,
    env: Mapping[str, str] | None = None,
    name: str | None = None,
    hooks: Hooks | None = None,
    collect_args: bool | None = None,
    signal: AbortSignal | None = None,
    timeouts: Timeouts | None = None,
) -> InteractiveResult:
    """Run an interactive agent session in ``worktree``."""
    from eden.orchestrator.interactive import interactive

    return interactive(
        agent=agent,
        sandbox=sandbox,
        prompt=prompt,
        prompt_file=prompt_file,
        prompt_args=prompt_args,
        env=env,
        name=name,
        hooks=hooks,
        collect_args=collect_args,
        signal=signal,
        timeouts=timeouts,
        _existing_worktree=worktree,
    )


__all__ = [
    "create_worktree_sandbox",
    "interactive_in_worktree",
    "run_in_worktree",
]
