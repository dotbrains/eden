"""Close helpers for worktree handles."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from eden.worktree._handle_protocols import StatusPorcelain, WorktreeRemove
from eden.worktree._lock import _LockHandle

CloseAction = Literal["removed", "preserved", "released_only"]


def close_worktree_handle(
    *,
    closed: list[bool],
    managed: bool,
    worktree_path: Path,
    host_repo_path: Path,
    lock_handle: _LockHandle,
    git_timeout: float,
    status_porcelain: StatusPorcelain,
    worktree_remove: WorktreeRemove,
) -> tuple[CloseAction, str | None]:
    if closed[0]:
        return "released_only", "already-closed"
    closed[0] = True
    try:
        if not managed:
            return "released_only", None
        dirty = bool(status_porcelain(repo_path=worktree_path, timeout=git_timeout).strip())
        if dirty:
            print(f"eden: leaving dirty worktree on disk at {worktree_path}")
            return "preserved", "dirty"
        worktree_remove(
            repo_path=host_repo_path,
            worktree_path=worktree_path,
            timeout=git_timeout,
        )
        return "removed", None
    finally:
        lock_handle.release()


__all__ = ["close_worktree_handle"]
