"""Worktree creation collision tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from eden.providers._types import BranchStrategy
from eden.worktree._create import create_worktree
from eden.worktree._git import list_worktrees
from eden.worktree.errors import WorktreeCollision

pytestmark = pytest.mark.unit


def test_create_worktree_blocks_when_branch_already_checked_out(tmp_git_repo: Path) -> None:
    # First worktree carves eden/foo successfully.
    h1 = create_worktree(
        host_repo_path=tmp_git_repo,
        strategy=BranchStrategy.named("eden/foo"),
    )
    try:
        # A second attempt at the same branch raises BranchExists —
        # branch_exists is true, so BranchExists fires first.
        from eden.worktree.errors import BranchExists

        with pytest.raises(BranchExists):
            create_worktree(
                host_repo_path=tmp_git_repo,
                strategy=BranchStrategy.named("eden/foo"),
            )
    finally:
        h1.close()


def test_create_worktree_blocks_when_branch_used_by_other_worktree(
    tmp_git_repo: Path,
) -> None:
    """Raw git-created worktrees are visible to Eden's worktree listing."""
    other_branch = "feature/dev"
    other_wt = tmp_git_repo / "other-wt"
    subprocess.run(
        ["git", "worktree", "add", "-b", other_branch, str(other_wt)],
        cwd=tmp_git_repo,
        check=True,
        capture_output=True,
    )

    records = list_worktrees(repo_path=tmp_git_repo)
    assert any(r.branch == other_branch for r in records)


def test_create_worktree_blocks_during_rebase(tmp_git_repo: Path) -> None:
    """Mid-rebase markers should produce WorktreeCollision."""
    (tmp_git_repo / ".git" / "rebase-merge").mkdir()
    try:
        with pytest.raises(WorktreeCollision) as exc_info:
            create_worktree(
                host_repo_path=tmp_git_repo,
                strategy=BranchStrategy.named("eden/wants-rebase-to-finish"),
            )
        assert exc_info.value.reason == "rebase_in_progress"
        assert "rebase --abort" in (exc_info.value.hint or "")
    finally:
        (tmp_git_repo / ".git" / "rebase-merge").rmdir()


def test_create_worktree_blocks_during_merge(tmp_git_repo: Path) -> None:
    (tmp_git_repo / ".git" / "MERGE_HEAD").write_text("aaa\n")
    try:
        with pytest.raises(WorktreeCollision) as exc_info:
            create_worktree(
                host_repo_path=tmp_git_repo,
                strategy=BranchStrategy.named("eden/wants-merge-to-finish"),
            )
        assert exc_info.value.reason == "rebase_in_progress"
        assert exc_info.value.conflict_path is not None
        assert exc_info.value.conflict_path.name == "MERGE_HEAD"
    finally:
        (tmp_git_repo / ".git" / "MERGE_HEAD").unlink()


def test_create_worktree_blocks_during_cherry_pick(tmp_git_repo: Path) -> None:
    (tmp_git_repo / ".git" / "CHERRY_PICK_HEAD").write_text("bbb\n")
    try:
        with pytest.raises(WorktreeCollision):
            create_worktree(
                host_repo_path=tmp_git_repo,
                strategy=BranchStrategy.named("eden/cherry"),
            )
    finally:
        (tmp_git_repo / ".git" / "CHERRY_PICK_HEAD").unlink()
