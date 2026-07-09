"""Lifecycle helpers for reusable sandbox wrappers."""

from __future__ import annotations

from collections.abc import Mapping

from eden._types import Timeouts
from eden.lifecycle import HookPhase, Hooks
from eden.lifecycle._runner import run_host_hooks, run_sandbox_hooks
from eden.providers._protocols import SandboxHandle
from eden.worktree._create import CloseResult, WorktreeHandle


def _close_worktree_best_effort(worktree: WorktreeHandle) -> None:
    try:
        worktree.close()
    except Exception as cleanup_exc:
        print(f"eden: worktree close also failed: {cleanup_exc}")


def close_sandbox(
    *,
    worktree: WorktreeHandle,
    handle: SandboxHandle,
    owns_worktree: bool,
    hooks: Hooks,
    create_env: Mapping[str, str],
    timeouts: Timeouts,
) -> CloseResult:
    """Close hooks, sandbox handle, and owned worktree in precedence order."""
    try:
        run_sandbox_hooks(
            phase=HookPhase.OnClose,
            hooks=hooks.sandbox,
            handle=handle,
            env=create_env,
            timeouts=timeouts,
        )
        run_host_hooks(
            phase=HookPhase.OnClose,
            hooks=hooks.host,
            worktree_path=worktree.worktree_path,
            env=create_env,
            timeouts=timeouts,
        )
    except BaseException:
        try:
            handle.close()
        finally:
            if owns_worktree:
                _close_worktree_best_effort(worktree)
        raise
    try:
        handle.close()
    except BaseException:
        if owns_worktree:
            _close_worktree_best_effort(worktree)
        raise
    if owns_worktree:
        return worktree.close()
    return CloseResult(action="released_only", reason="caller-owned-worktree")


__all__ = ["close_sandbox"]
