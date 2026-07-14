"""Worktree manager — public surface."""

from __future__ import annotations

from eden.worktree._create import create_worktree
from eden.worktree._git import head_sha, new_commits
from eden.worktree._handle import WorktreeHandle
from eden.worktree._handle_result import CloseResult

__all__ = ["CloseResult", "WorktreeHandle", "create_worktree", "head_sha", "new_commits"]
