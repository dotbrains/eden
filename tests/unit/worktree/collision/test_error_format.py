"""Worktree collision error formatting tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from eden.worktree.errors import WorktreeCollision

pytestmark = pytest.mark.unit


def test_worktree_collision_exposes_recovery_hint() -> None:
    err = WorktreeCollision(
        branch="eden/x",
        reason="branch_in_use",
        conflict_path=Path("/repo/.eden/worktrees/eden-x"),
        hint="remove the colliding worktree",
    )
    assert err.branch == "eden/x"
    assert err.reason == "branch_in_use"
    assert "remove the colliding worktree" in str(err)


def test_worktree_collision_in_error_format() -> None:
    """The centralized formatter surfaces the WorktreeCollision hint."""
    from eden import format_error_message

    err = WorktreeCollision(
        branch="eden/x",
        reason="rebase_in_progress",
        conflict_path=Path("/repo/.git/MERGE_HEAD"),
        hint="run `git merge --abort` first",
    )
    out = format_error_message(err)
    assert "Git worktree operation failed" in out
    assert "rebase_in_progress" in out
    assert "git merge --abort" in out
