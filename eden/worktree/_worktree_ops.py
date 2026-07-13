"""Git worktree add/remove operations and collision checks."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from eden.worktree._git import _DEFAULT_GIT_TIMEOUT, _NO_CONFIG_LOCK_FLAGS, _run_git
from eden.worktree._state import detect_in_progress, parse_worktree_list
from eden.worktree.errors import WorktreeCollision

_WORKTREE_MUTEXES: dict[Path, threading.Lock] = {}
_WORKTREE_MUTEXES_GUARD = threading.Lock()


@contextmanager
def _git_worktree_mutex(repo_path: Path) -> Iterator[None]:
    """Serialize Git worktree metadata mutations within this process."""
    key = repo_path.resolve()
    with _WORKTREE_MUTEXES_GUARD:
        lock = _WORKTREE_MUTEXES.setdefault(key, threading.Lock())
    with lock:
        yield


def _check_collisions(
    *, repo_path: Path, branch: str, timeout: float = _DEFAULT_GIT_TIMEOUT
) -> None:
    """Raise WorktreeCollision if ``git worktree add`` would conflict."""
    in_progress = detect_in_progress(repo_path=repo_path)
    if in_progress is not None:
        raise WorktreeCollision(
            branch=branch,
            reason="rebase_in_progress",
            conflict_path=in_progress,
            hint=(
                "finish or abort the in-flight git operation before carving a new "
                "worktree (`git rebase --abort` / `git merge --abort` / "
                "`git cherry-pick --abort`)."
            ),
        )
    stdout, _ = _run_git(("git", "worktree", "list", "--porcelain"), cwd=repo_path, timeout=timeout)
    for record in parse_worktree_list(stdout):
        if record.branch == branch:
            raise WorktreeCollision(
                branch=branch,
                reason="branch_in_use",
                conflict_path=record.path,
                hint=(
                    f"branch {branch!r} is already checked out at {record.path}; "
                    "remove that worktree or pick a different branch."
                ),
            )


def worktree_add(
    *,
    repo_path: Path,
    worktree_path: Path,
    branch: str,
    base: str,
    timeout: float = _DEFAULT_GIT_TIMEOUT,
) -> None:
    with _git_worktree_mutex(repo_path):
        _check_collisions(repo_path=repo_path, branch=branch, timeout=timeout)
        _run_git(
            (
                "git",
                *_NO_CONFIG_LOCK_FLAGS,
                "worktree",
                "add",
                "-b",
                branch,
                str(worktree_path),
                base,
            ),
            cwd=repo_path,
            timeout=timeout,
        )


def worktree_remove(
    *, repo_path: Path, worktree_path: Path, timeout: float = _DEFAULT_GIT_TIMEOUT
) -> None:
    with _git_worktree_mutex(repo_path):
        _run_git(
            ("git", "worktree", "remove", "--force", str(worktree_path)),
            cwd=repo_path,
            timeout=timeout,
        )


__all__ = ["worktree_add", "worktree_remove"]
