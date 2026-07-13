"""Thin wrappers around git commands the worktree manager runs."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import eden.worktree._commit_state as _commit_state
from eden.worktree._state import (
    IN_PROGRESS_MARKERS,
    WorktreeRecord,
    detect_in_progress,
    parse_worktree_list,
)
from eden.worktree.errors import GitCommandFailed, GitCommandTimeout

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
