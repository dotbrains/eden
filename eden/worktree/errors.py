"""Worktree-specific exceptions."""

from __future__ import annotations

from pathlib import Path

from eden.errors import EdenError


class WorktreeError(EdenError):
    """Base for worktree errors."""


class WorktreeLocked(WorktreeError):
    def __init__(self, *, lock_path: Path, holder_pid: int) -> None:
        self.lock_path = lock_path
        self.holder_pid = holder_pid
        super().__init__(f"worktree lock at {lock_path} held by pid {holder_pid}")


class DirtyHostBlocked(WorktreeError):
    def __init__(self, *, host_repo_path: Path, dirty_files: tuple[str, ...]) -> None:
        self.host_repo_path = host_repo_path
        self.dirty_files = dirty_files
        joined = ", ".join(dirty_files[:10]) or "(unknown)"
        super().__init__(f"host repo {host_repo_path} has uncommitted changes: {joined}")


class BranchExists(WorktreeError):
    def __init__(self, *, branch: str) -> None:
        self.branch = branch
        super().__init__(f"branch {branch!r} already exists")


class GitCommandFailed(WorktreeError):
    def __init__(self, *, argv: tuple[str, ...], exit_code: int, stderr: str) -> None:
        self.argv = argv
        self.exit_code = exit_code
        self.stderr = stderr
        super().__init__(f"git command failed (exit {exit_code}): {' '.join(argv)}\n{stderr}")
