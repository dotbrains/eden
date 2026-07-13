"""Lifecycle hook runners for loop iterations."""

from __future__ import annotations

from eden._types import Timeouts
from eden.lifecycle import HookPhase, Hooks
from eden.lifecycle._runner import run_host_hooks, run_sandbox_hooks
from eden.providers._protocols import SandboxHandle
from eden.worktree._create import WorktreeHandle


def run_iteration_start_hooks(
    *,
    hooks: Hooks,
    handle: SandboxHandle,
    worktree: WorktreeHandle,
    env: dict[str, str],
    timeouts: Timeouts,
) -> None:
    run_host_hooks(
        phase=HookPhase.OnIterationStart,
        hooks=hooks.host,
        worktree_path=worktree.worktree_path,
        env=env,
        timeouts=timeouts,
    )
    run_sandbox_hooks(
        phase=HookPhase.OnIterationStart,
        hooks=hooks.sandbox,
        handle=handle,
        env=env,
        timeouts=timeouts,
    )


def run_iteration_end_hooks(
    *,
    hooks: Hooks,
    handle: SandboxHandle,
    worktree: WorktreeHandle,
    env: dict[str, str],
    timeouts: Timeouts,
) -> None:
    run_sandbox_hooks(
        phase=HookPhase.OnIterationEnd,
        hooks=hooks.sandbox,
        handle=handle,
        env=env,
        timeouts=timeouts,
    )
    run_host_hooks(
        phase=HookPhase.OnIterationEnd,
        hooks=hooks.host,
        worktree_path=worktree.worktree_path,
        env=env,
        timeouts=timeouts,
    )


__all__ = ["run_iteration_end_hooks", "run_iteration_start_hooks"]
