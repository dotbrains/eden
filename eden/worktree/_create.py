"""Worktree manager: create_worktree, WorktreeHandle, CloseResult."""

from __future__ import annotations

import datetime as _dt
import re
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from eden.providers._types import BranchStrategy
from eden.worktree._git import (
    branch_exists,
    status_porcelain,
    worktree_add,
    worktree_remove,
)
from eden.worktree._lock import _LockHandle, acquire_lock
from eden.worktree.errors import BranchExists, DirtyHostBlocked

_SANITIZE_RE = re.compile(r"[^a-z0-9._-]+")


def _sanitize(name: str) -> str:
    s = _SANITIZE_RE.sub("-", name.lower()).strip("-")
    return s or "x"


@dataclass(frozen=True)
class CloseResult:
    action: Literal["removed", "preserved", "released_only"]
    reason: str | None = None


@dataclass(frozen=True)
class WorktreeHandle:
    branch: str
    worktree_path: Path
    host_repo_path: Path
    managed: bool
    _lock_handle: _LockHandle = field(repr=False)
    _closed: list[bool] = field(default_factory=lambda: [False], repr=False)

    def __enter__(self) -> WorktreeHandle:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> CloseResult:
        if self._closed[0]:
            return CloseResult(action="released_only", reason="already-closed")
        self._closed[0] = True
        try:
            if not self.managed:
                return CloseResult(action="released_only")
            dirty = bool(status_porcelain(repo_path=self.worktree_path).strip())
            if dirty:
                print(f"eden: leaving dirty worktree on disk at {self.worktree_path}")
                return CloseResult(action="preserved", reason="dirty")
            worktree_remove(
                repo_path=self.host_repo_path,
                worktree_path=self.worktree_path,
            )
            return CloseResult(action="removed")
        finally:
            self._lock_handle.release()


def _generate_branch(name_hint: str | None) -> str:
    suffix = secrets.token_hex(4)
    if name_hint:
        return f"eden/{_sanitize(name_hint)}-{suffix}"
    ts = _dt.datetime.now().strftime("%Y%m%d%H%M%S")
    return f"eden/{ts}-{suffix}"


def _lock_path_for(host_repo_path: Path, branch: str | None) -> Path:
    base = host_repo_path / ".eden" / "worktrees"
    if branch is None:
        return base / "_head.lock"
    return base / f"{_sanitize(branch)}.lock"


def _worktree_path_for(host_repo_path: Path, branch: str) -> Path:
    return host_repo_path / ".eden" / "worktrees" / _sanitize(branch)


def _ensure_eden_gitignore(host_repo_path: Path) -> None:
    """Write .eden/.gitignore so git ignores eden's own metadata directory."""
    eden_dir = host_repo_path / ".eden"
    eden_dir.mkdir(exist_ok=True)
    gitignore = eden_dir / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("*\n", encoding="utf-8")


def create_worktree(
    *,
    host_repo_path: Path,
    strategy: BranchStrategy,
    name_hint: str | None = None,
) -> WorktreeHandle:
    # Ensure .eden/ is gitignored regardless of strategy so metadata files
    # created by any path don't surface as untracked in the host repo.
    _ensure_eden_gitignore(host_repo_path)

    if strategy.tag == "head":
        dirty = status_porcelain(repo_path=host_repo_path).strip()
        if dirty:
            files = tuple(line[3:] for line in dirty.splitlines() if len(line) > 3)[:10]
            raise DirtyHostBlocked(host_repo_path=host_repo_path, dirty_files=files)
        lock = acquire_lock(_lock_path_for(host_repo_path, None))
        return WorktreeHandle(
            branch="HEAD",
            worktree_path=host_repo_path,
            host_repo_path=host_repo_path,
            managed=False,
            _lock_handle=lock,
        )

    if strategy.tag == "merge_to_head":
        branch = _generate_branch(name_hint)
    else:  # named
        assert strategy.branch is not None
        branch = strategy.branch
        if branch_exists(repo_path=host_repo_path, branch=branch):
            raise BranchExists(branch=branch)

    wt_path = _worktree_path_for(host_repo_path, branch)
    lock = acquire_lock(_lock_path_for(host_repo_path, branch))
    try:
        worktree_add(
            repo_path=host_repo_path,
            worktree_path=wt_path,
            branch=branch,
            base=strategy.base,
        )
    except Exception:
        lock.release()
        raise

    return WorktreeHandle(
        branch=branch,
        worktree_path=wt_path,
        host_repo_path=host_repo_path,
        managed=True,
        _lock_handle=lock,
    )
