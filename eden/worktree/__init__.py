"""Worktree manager — public surface."""

from __future__ import annotations

from eden.worktree._create import (
    CloseResult,
    WorktreeHandle,
    create_worktree,
)
from eden.worktree._git import head_sha, new_commits

__all__ = ["CloseResult", "WorktreeHandle", "create_worktree", "head_sha", "new_commits"]
