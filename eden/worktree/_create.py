from __future__ import annotations

import datetime as _dt
import re
import secrets
from pathlib import Path

from eden.providers._types import BranchStrategy
from eden.worktree._git import _DEFAULT_GIT_TIMEOUT, branch_exists, status_porcelain
from eden.worktree._handle import WorktreeHandle
from eden.worktree._handle_result import CloseResult
from eden.worktree._lock import acquire_lock
from eden.worktree._reuse import checked_out_path, duplicate_branch_hint, find_reusable_worktree
from eden.worktree._worktree_ops import worktree_add, worktree_remove
from eden.worktree.errors import BranchExists, DirtyHostBlocked

__all__ = [
    "CloseResult",
    "WorktreeHandle",
    "_eden_dir",
    "_lock_path_for",
    "_worktree_path_for",
    "create_worktree",
]

_SANITIZE_RE = re.compile(r"[^a-z0-9._-]+")


def _sanitize(name: str) -> str:
    s = _SANITIZE_RE.sub("-", name.lower()).strip("-")
    return s or "x"


def _generate_branch(name_hint: str | None) -> str:
    suffix = secrets.token_hex(4)
    if name_hint:
        return f"eden/{_sanitize(name_hint)}-{suffix}"
    ts = _dt.datetime.now().strftime("%Y%m%d%H%M%S")
    return f"eden/{ts}-{suffix}"


def _eden_dir(host_repo_path: Path) -> Path:
    """Return the resolved (symlink-free) path to ``<repo>/.eden/``.

    Git keys its worktree records by realpath. When users symlink
    ``.eden/`` to another disk (a common setup when the host repo lives
    on a small SSD), passing the symlink-relative path to
    ``git worktree add / remove`` makes git's internal lookup miss records.

    The directory is created if it does not exist so ``.resolve()``
    returns an absolute path on every platform (Windows in particular
    requires the target to exist for full resolution).
    """
    eden_dir = host_repo_path / ".eden"
    eden_dir.mkdir(exist_ok=True)
    return eden_dir.resolve()


def _lock_path_for(host_repo_path: Path, branch: str | None) -> Path:
    base = _eden_dir(host_repo_path) / "worktrees"
    if branch is None:
        return base / "_head.lock"
    return base / f"{_sanitize(branch)}.lock"


def _worktree_path_for(host_repo_path: Path, branch: str) -> Path:
    return _eden_dir(host_repo_path) / "worktrees" / _sanitize(branch)


def _ensure_eden_gitignore(host_repo_path: Path) -> None:
    eden_dir = _eden_dir(host_repo_path)
    gitignore = eden_dir / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("*\n", encoding="utf-8")


def create_worktree(
    *,
    host_repo_path: Path,
    strategy: BranchStrategy,
    name_hint: str | None = None,
    throw_on_duplicate_worktree: bool = True,
    git_timeout: float = _DEFAULT_GIT_TIMEOUT,
) -> WorktreeHandle:
    """Carve (or reuse) a worktree per ``strategy``.

    ``git_timeout`` is the per-command deadline for every host-side git
    invocation this carve runs; it is also stored on the returned handle so
    ``close()`` reuses it for the teardown ``git worktree remove``. Callers
    in the run loop pass ``Timeouts.git_setup``.
    """
    _ensure_eden_gitignore(host_repo_path)

    if strategy.tag == "head":
        dirty = status_porcelain(repo_path=host_repo_path, timeout=git_timeout).strip()
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
            _git_timeout=git_timeout,
            _status_porcelain=status_porcelain,
            _worktree_remove=worktree_remove,
        )

    if strategy.tag == "merge_to_head":
        branch = _generate_branch(name_hint)
    else:  # named
        assert strategy.branch is not None
        branch = strategy.branch
        if branch_exists(repo_path=host_repo_path, branch=branch, timeout=git_timeout):
            conflict_path = checked_out_path(
                repo_path=host_repo_path,
                branch=branch,
                timeout=git_timeout,
            )
            if throw_on_duplicate_worktree:
                raise BranchExists(
                    branch=branch,
                    conflict_path=conflict_path,
                    hint=duplicate_branch_hint() if conflict_path is not None else None,
                )
            # Reuse path: find the existing worktree for this branch.
            reusable = find_reusable_worktree(
                host_repo_path=host_repo_path,
                branch=branch,
                lock_path=_lock_path_for(host_repo_path, branch),
                git_timeout=git_timeout,
            )
            if reusable is not None:
                return reusable
            # Branch exists but isn't checked out by any worktree — we have
            # no on-disk worktree to reuse. Fall through to BranchExists so
            # the caller knows their state is unexpected.
            raise BranchExists(branch=branch)

    wt_path = _worktree_path_for(host_repo_path, branch)
    lock = acquire_lock(_lock_path_for(host_repo_path, branch))
    try:
        worktree_add(
            repo_path=host_repo_path,
            worktree_path=wt_path,
            branch=branch,
            base=strategy.base,
            timeout=git_timeout,
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
        _git_timeout=git_timeout,
        _status_porcelain=status_porcelain,
        _worktree_remove=worktree_remove,
    )
