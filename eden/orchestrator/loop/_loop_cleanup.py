"""Cleanup helpers for the orchestrator loop."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import ExitStack
from pathlib import Path

from opentelemetry import trace

from eden._types import Commit, Timeouts
from eden.lifecycle import HookPhase, Hooks
from eden.lifecycle._runner import run_host_hooks, run_sandbox_hooks
from eden.orchestrator._logging import LoopLogger
from eden.providers._protocols import SandboxHandle
from eden.tracing import set_attributes
from eden.worktree._create import WorktreeHandle
from eden.worktree._git import new_commits


def close_loop_resources(
    *,
    unregister_shutdown: Callable[[], None] | None,
    handle: SandboxHandle | None,
    caller_managed: bool,
    hooks: Hooks,
    worktree: WorktreeHandle,
    env: dict[str, str],
    timeouts: Timeouts,
    logger: LoopLogger | None,
    commit_base_sha: str,
    completion_hit: str | None,
    iteration_count: int,
    run_span: trace.Span,
    stack: ExitStack,
) -> tuple[list[Commit], Path | None]:
    if unregister_shutdown is not None:
        try:
            unregister_shutdown()
        except Exception:
            pass
    if handle is not None and not caller_managed:
        try:
            run_sandbox_hooks(
                phase=HookPhase.OnClose,
                hooks=hooks.sandbox,
                handle=handle,
                env=env,
                timeouts=timeouts,
            )
        except Exception:
            pass
    if not caller_managed:
        try:
            run_host_hooks(
                phase=HookPhase.OnClose,
                hooks=hooks.host,
                worktree_path=worktree.worktree_path,
                env=env,
                timeouts=timeouts,
            )
        except Exception:
            pass
    if handle is not None and not caller_managed:
        try:
            handle.close()
        except Exception:
            pass
    if logger is not None:
        logger.close()
    collected_commits = [
        Commit(sha=sha)
        for sha in new_commits(
            worktree_path=worktree.worktree_path,
            base_sha=commit_base_sha,
            timeout=timeouts.commit_collection,
        )
    ]
    preserved: Path | None = None
    if not caller_managed:
        close_result = worktree.close()
        if close_result.action == "preserved":
            preserved = worktree.worktree_path
    set_attributes(
        run_span,
        {
            "iterations": iteration_count,
            "completion_signal": completion_hit,
        },
    )
    stack.close()
    return collected_commits, preserved


__all__ = ["close_loop_resources"]
