"""Cleanup helpers for ``eden.interactive()``."""

from __future__ import annotations

from eden._types import Timeouts
from eden.lifecycle import HookPhase, Hooks
from eden.lifecycle._runner import run_host_hooks, run_sandbox_hooks
from eden.providers._protocols import SandboxHandle
from eden.worktree._create import WorktreeHandle


def close_interactive_resources(
    *,
    handle: SandboxHandle | None,
    worktree: WorktreeHandle,
    hooks: Hooks,
    env: dict[str, str],
    timeouts: Timeouts,
    close_worktree: bool,
) -> None:
    if handle is not None:
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
    if handle is not None:
        try:
            handle.close()
        except Exception:
            pass
    if close_worktree:
        worktree.close()


__all__ = ["close_interactive_resources"]
