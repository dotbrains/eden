"""Worktree manager — public surface."""

from __future__ import annotations

from eden.worktree._create import (
    CloseResult,
    WorktreeHandle,
    create_worktree,
)

__all__ = ["CloseResult", "WorktreeHandle", "create_worktree"]
