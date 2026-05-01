"""Thin wrappers around git commands the worktree manager runs."""

from __future__ import annotations

import subprocess
from pathlib import Path

from eden.worktree.errors import GitCommandFailed


def _run_git(argv: tuple[str, ...], *, cwd: Path) -> tuple[str, str]:
    proc = subprocess.run(
        argv,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise GitCommandFailed(argv=argv, exit_code=proc.returncode, stderr=proc.stderr)
    return proc.stdout, proc.stderr


def status_porcelain(*, repo_path: Path) -> str:
    stdout, _ = _run_git(("git", "status", "--porcelain"), cwd=repo_path)
    return stdout


def branch_exists(*, repo_path: Path, branch: str) -> bool:
    proc = subprocess.run(
        ("git", "rev-parse", "--verify", f"refs/heads/{branch}"),
        cwd=str(repo_path),
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode == 0


def worktree_add(
    *,
    repo_path: Path,
    worktree_path: Path,
    branch: str,
    base: str,
) -> None:
    _run_git(
        (
            "git",
            "worktree",
            "add",
            "-b",
            branch,
            str(worktree_path),
            base,
        ),
        cwd=repo_path,
    )


def worktree_remove(*, repo_path: Path, worktree_path: Path) -> None:
    _run_git(
        ("git", "worktree", "remove", "--force", str(worktree_path)),
        cwd=repo_path,
    )
