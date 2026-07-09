"""Thin wrappers around git commands the worktree manager runs."""

from __future__ import annotations

import os
import subprocess
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import eden.worktree._commit_state as _commit_state
from eden.worktree._state import (
    IN_PROGRESS_MARKERS,
    WorktreeRecord,
    detect_in_progress,
    parse_worktree_list,
)
from eden.worktree.errors import GitCommandFailed, GitCommandTimeout, WorktreeCollision

# All host-side git invocations bound by this deadline. A wedged local
# git (NFS stall, filesystem repair, runaway hook) would otherwise hang
# Eden indefinitely.
_DEFAULT_GIT_TIMEOUT: float = 60.0

# Prevent ``git worktree add -b`` from writing upstream tracking config into
# ``.git/config`` when user-level branch auto-setup is enabled. That avoids
# needless ``.git/config.lock`` contention during parallel Eden runs.
_NO_CONFIG_LOCK_FLAGS: tuple[str, ...] = (
    "-c",
    "branch.autoSetupMerge=false",
    "-c",
    "push.autoSetupRemote=false",
)
_WORKTREE_MUTEXES: dict[Path, threading.Lock] = {}
_WORKTREE_MUTEXES_GUARD = threading.Lock()


@contextmanager
def _git_worktree_mutex(repo_path: Path) -> Iterator[None]:
    """Serialize Git worktree metadata mutations within this process.

    Git itself writes multiple files under ``.git/worktrees`` during
    ``worktree add/remove``. On macOS Git 2.54, two concurrent adds can observe
    each other's half-written metadata and fail while reading ``commondir``.
    Eden branch locks are intentionally per branch, so add this narrow mutex
    around the Git mutation while preserving concurrency for the agent runs.
    """
    key = repo_path.resolve()
    with _WORKTREE_MUTEXES_GUARD:
        lock = _WORKTREE_MUTEXES.setdefault(key, threading.Lock())
    with lock:
        yield


def c_locale_env() -> dict[str, str]:
    """Inherit ``os.environ`` and pin git's locale to ``C``.

    Eden parses git output via ``--porcelain`` and exit codes today, so
    the immediate motivation is defensive: a future caller that
    substring-matches human-readable stderr (e.g. "fatal: invalid
    reference") would silently break under non-English locales without
    this pin.

    ``LANGUAGE`` is cleared because git prefers it over ``LC_ALL`` for
    message selection.
    """
    return {**os.environ, "LC_ALL": "C", "LANG": "C", "LANGUAGE": ""}


def _run_git(
    argv: tuple[str, ...],
    *,
    cwd: Path,
    timeout: float = _DEFAULT_GIT_TIMEOUT,
) -> tuple[str, str]:
    try:
        proc = subprocess.run(
            argv,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
            env=c_locale_env(),
        )
    except subprocess.TimeoutExpired as exc:
        raise GitCommandTimeout(argv=argv, timeout=timeout) from exc
    if proc.returncode != 0:
        raise GitCommandFailed(argv=argv, exit_code=proc.returncode, stderr=proc.stderr)
    return proc.stdout, proc.stderr


def status_porcelain(*, repo_path: Path, timeout: float = _DEFAULT_GIT_TIMEOUT) -> str:
    stdout, _ = _run_git(("git", "status", "--porcelain"), cwd=repo_path, timeout=timeout)
    return stdout


def branch_exists(*, repo_path: Path, branch: str, timeout: float = _DEFAULT_GIT_TIMEOUT) -> bool:
    try:
        proc = subprocess.run(
            ("git", "rev-parse", "--verify", f"refs/heads/{branch}"),
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
            env=c_locale_env(),
        )
    except subprocess.TimeoutExpired as exc:
        raise GitCommandTimeout(
            argv=("git", "rev-parse", "--verify", f"refs/heads/{branch}"),
            timeout=timeout,
        ) from exc
    return proc.returncode == 0


_IN_PROGRESS_MARKERS = IN_PROGRESS_MARKERS
_WorktreeRecord = WorktreeRecord
_detect_in_progress = detect_in_progress
_parse_worktree_list = parse_worktree_list


def list_worktrees(
    *, repo_path: Path, timeout: float = _DEFAULT_GIT_TIMEOUT
) -> tuple[WorktreeRecord, ...]:
    """Return every worktree git knows about for ``repo_path``."""
    stdout, _ = _run_git(("git", "worktree", "list", "--porcelain"), cwd=repo_path, timeout=timeout)
    return parse_worktree_list(stdout)


def _check_collisions(
    *, repo_path: Path, branch: str, timeout: float = _DEFAULT_GIT_TIMEOUT
) -> None:
    """Raise WorktreeCollision if ``git worktree add`` would conflict.

    Two conditions are detected up front so the caller sees a structured
    error rather than a cryptic git stderr dump:

    * the host repo is mid-rebase / mid-merge / mid-cherry-pick;
    * the target ``branch`` is already checked out by another worktree.
    """
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
    for record in list_worktrees(repo_path=repo_path, timeout=timeout):
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


def head_sha(*, repo_path: Path, timeout: float = _DEFAULT_GIT_TIMEOUT) -> str:
    return _commit_state.head_sha(run_git=_run_git, repo_path=repo_path, timeout=timeout)


def new_commits(
    *, worktree_path: Path, base_sha: str, timeout: float = _DEFAULT_GIT_TIMEOUT
) -> tuple[str, ...]:
    return _commit_state.new_commits(
        run_git=_run_git,
        worktree_path=worktree_path,
        base_sha=base_sha,
        timeout=timeout,
    )


def refresh_from_origin(
    *, worktree_path: Path, branch: str, timeout: float = _DEFAULT_GIT_TIMEOUT
) -> None:
    return _commit_state.refresh_from_origin(
        run_git=_run_git,
        no_config_lock_flags=_NO_CONFIG_LOCK_FLAGS,
        worktree_path=worktree_path,
        branch=branch,
        timeout=timeout,
    )
