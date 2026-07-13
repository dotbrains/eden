"""Reusable named-worktree lookup."""

from __future__ import annotations

from pathlib import Path

from eden.worktree._git import (
    _DEFAULT_GIT_TIMEOUT,
    list_worktrees,
    refresh_from_origin,
    status_porcelain,
)
from eden.worktree._handle import WorktreeHandle
from eden.worktree._lock import acquire_lock
from eden.worktree._worktree_ops import worktree_remove


def find_reusable_worktree(
    *,
    host_repo_path: Path,
    branch: str,
    lock_path: Path,
    git_timeout: float = _DEFAULT_GIT_TIMEOUT,
) -> WorktreeHandle | None:
    """Return an unmanaged handle for an existing checked-out branch."""
    for record in list_worktrees(repo_path=host_repo_path, timeout=git_timeout):
        if record.branch != branch:
            continue

        lock = acquire_lock(lock_path)
        has_changes = bool(status_porcelain(repo_path=record.path, timeout=git_timeout).strip())
        if has_changes:
            print(
                f"eden: reusing worktree at {record.path} "
                f"(branch {branch!r}) — worktree has uncommitted changes"
            )
        else:
            refresh_from_origin(worktree_path=record.path, branch=branch, timeout=git_timeout)
        return WorktreeHandle(
            branch=branch,
            worktree_path=record.path,
            host_repo_path=host_repo_path,
            managed=False,
            _lock_handle=lock,
            _git_timeout=git_timeout,
            _status_porcelain=status_porcelain,
            _worktree_remove=worktree_remove,
        )

    return None


__all__ = ["find_reusable_worktree"]
