"""Verify worktree refresh and reuse edge cases."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from eden.providers._types import BranchStrategy
from eden.worktree._create import create_worktree
from eden.worktree._git import refresh_from_origin
from eden.worktree.errors import BranchExists
from tests.unit.worktree_strategy_helpers import advance_origin, git

pytestmark = pytest.mark.unit


def test_refresh_from_origin_fast_forwards_behind_worktree(tmp_git_repo: Path) -> None:
    """A clean worktree strictly behind origin/<branch> is fast-forwarded."""
    origin = tmp_git_repo.parent / "origin.git"
    git(tmp_git_repo, "clone", "--bare", str(tmp_git_repo), str(origin))

    wt = create_worktree(
        host_repo_path=tmp_git_repo,
        strategy=BranchStrategy.named("feat/ff"),
    )
    try:
        git(wt.worktree_path, "remote", "add", "origin", str(origin))
        git(wt.worktree_path, "push", "origin", "feat/ff")
        head_before = git(wt.worktree_path, "rev-parse", "HEAD")
        advance_origin(origin, tmp_git_repo.parent, "feat/ff")

        refresh_from_origin(worktree_path=wt.worktree_path, branch="feat/ff")

        head_after = git(wt.worktree_path, "rev-parse", "HEAD")
        assert head_after != head_before
        assert (wt.worktree_path / "ahead.txt").exists()
    finally:
        wt.close()


def test_refresh_from_origin_without_origin_is_noop(tmp_git_repo: Path) -> None:
    """No origin remote -> reuse the worktree as-is, never raising."""
    wt = create_worktree(
        host_repo_path=tmp_git_repo,
        strategy=BranchStrategy.named("feat/no-origin"),
    )
    try:
        head_before = git(wt.worktree_path, "rev-parse", "HEAD")
        refresh_from_origin(worktree_path=wt.worktree_path, branch="feat/no-origin")
        assert git(wt.worktree_path, "rev-parse", "HEAD") == head_before
    finally:
        wt.close()


def test_refresh_from_origin_detached_head_skips(tmp_git_repo: Path) -> None:
    """A detached HEAD, such as a paused rebase, is left untouched."""
    origin = tmp_git_repo.parent / "origin3.git"
    git(tmp_git_repo, "clone", "--bare", str(tmp_git_repo), str(origin))

    wt = create_worktree(
        host_repo_path=tmp_git_repo,
        strategy=BranchStrategy.named("feat/detach"),
    )
    try:
        git(wt.worktree_path, "remote", "add", "origin", str(origin))
        git(wt.worktree_path, "push", "origin", "feat/detach")
        advance_origin(origin, tmp_git_repo.parent, "feat/detach")
        git(wt.worktree_path, "checkout", "--detach", "HEAD")
        head_before = git(wt.worktree_path, "rev-parse", "HEAD")

        refresh_from_origin(worktree_path=wt.worktree_path, branch="feat/detach")

        assert git(wt.worktree_path, "rev-parse", "HEAD") == head_before
    finally:
        wt.close()


def test_named_reuse_dirty_worktree_skips_refresh(tmp_git_repo: Path) -> None:
    """A dirty reused worktree is returned untouched, with no fetch or merge."""
    origin = tmp_git_repo.parent / "origin2.git"
    git(tmp_git_repo, "clone", "--bare", str(tmp_git_repo), str(origin))
    git(tmp_git_repo, "remote", "add", "origin", str(origin))

    first = create_worktree(
        host_repo_path=tmp_git_repo,
        strategy=BranchStrategy.named("feat/dirty"),
    )
    wt_path = first.worktree_path
    git(wt_path, "push", "origin", "feat/dirty")
    (wt_path / "uncommitted.txt").write_text("dirt")
    result = first.close()
    assert result.action == "preserved"

    second = create_worktree(
        host_repo_path=tmp_git_repo,
        strategy=BranchStrategy.named("feat/dirty"),
        throw_on_duplicate_worktree=False,
    )
    try:
        assert (second.worktree_path / "uncommitted.txt").read_text() == "dirt"
    finally:
        second.close()


def test_named_reuse_branch_without_worktree_raises(tmp_git_repo: Path) -> None:
    """Reuse path requires an actual on-disk worktree; bare branches still raise."""
    subprocess.run(
        ["git", "branch", "feat/bare"],
        cwd=str(tmp_git_repo),
        check=True,
        capture_output=True,
    )
    with pytest.raises(BranchExists):
        create_worktree(
            host_repo_path=tmp_git_repo,
            strategy=BranchStrategy.named("feat/bare"),
            throw_on_duplicate_worktree=False,
        )
