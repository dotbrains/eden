"""Helpers for worktree strategy unit tests."""

from __future__ import annotations

import subprocess
from pathlib import Path


def branch_of(worktree: Path) -> str:
    return git(worktree, "rev-parse", "--abbrev-ref", "HEAD")


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def advance_origin(origin: Path, repo_parent: Path, branch: str) -> None:
    """Push one extra commit to ``origin/<branch>`` via a throwaway clone."""
    clone = repo_parent / f"pusher-{branch.replace('/', '-')}"
    git(repo_parent, "clone", str(origin), str(clone))
    git(clone, "config", "user.email", "test@example.com")
    git(clone, "config", "user.name", "Test")
    git(clone, "config", "commit.gpgsign", "false")
    git(clone, "checkout", branch)
    (clone / "ahead.txt").write_text("ahead\n")
    git(clone, "add", "ahead.txt")
    git(clone, "commit", "-m", "advance origin")
    git(clone, "push", "origin", branch)
