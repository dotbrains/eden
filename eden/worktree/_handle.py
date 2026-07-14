from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from eden.worktree._git import _DEFAULT_GIT_TIMEOUT, status_porcelain
from eden.worktree._handle_close import close_worktree_handle
from eden.worktree._handle_methods import _WorktreeMethods
from eden.worktree._handle_protocols import StatusPorcelain, WorktreeRemove
from eden.worktree._handle_result import CloseResult
from eden.worktree._lock import _LockHandle
from eden.worktree._worktree_ops import worktree_remove


@dataclass(frozen=True)
class WorktreeHandle(_WorktreeMethods):
    branch: str
    worktree_path: Path
    host_repo_path: Path
    managed: bool
    _lock_handle: _LockHandle = field(repr=False)
    _closed: list[bool] = field(default_factory=lambda: [False], repr=False)
    _git_timeout: float = field(default=_DEFAULT_GIT_TIMEOUT, repr=False)
    _status_porcelain: StatusPorcelain = field(default=status_porcelain, repr=False)
    _worktree_remove: WorktreeRemove = field(default=worktree_remove, repr=False)

    def __enter__(self) -> WorktreeHandle:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> CloseResult:
        action, reason = close_worktree_handle(
            closed=self._closed,
            managed=self.managed,
            worktree_path=self.worktree_path,
            host_repo_path=self.host_repo_path,
            lock_handle=self._lock_handle,
            git_timeout=self._git_timeout,
            status_porcelain=self._status_porcelain,
            worktree_remove=self._worktree_remove,
        )
        return CloseResult(action=action, reason=reason)
