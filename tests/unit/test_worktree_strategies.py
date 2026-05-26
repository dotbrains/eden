"""Verify merge_to_head and named worktree strategies."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from eden.providers._types import BranchStrategy
from eden.worktree._create import create_worktree
from eden.worktree.errors import BranchExists

pytestmark = pytest.mark.unit


def _branch_of(repo: Path, worktree: Path) -> str:
    out = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=str(worktree),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return out


def test_merge_to_head_creates_managed_worktree(tmp_git_repo: Path) -> None:
    h = create_worktree(
        host_repo_path=tmp_git_repo,
        strategy=BranchStrategy.merge_to_head(),
    )
    try:
        assert h.managed is True
        assert h.branch.startswith("eden/")
        assert h.worktree_path.exists()
        assert h.worktree_path != tmp_git_repo
        assert _branch_of(tmp_git_repo, h.worktree_path) == h.branch
    finally:
        h.close()


def test_merge_to_head_uses_name_hint(tmp_git_repo: Path) -> None:
    h = create_worktree(
        host_repo_path=tmp_git_repo,
        strategy=BranchStrategy.merge_to_head(),
        name_hint="My Feature!",
    )
    try:
        assert h.branch.startswith("eden/my-feature-")
    finally:
        h.close()


def test_merge_to_head_close_removes_clean_worktree(
    tmp_git_repo: Path,
) -> None:
    h = create_worktree(
        host_repo_path=tmp_git_repo,
        strategy=BranchStrategy.merge_to_head(),
    )
    wt = h.worktree_path
    result = h.close()
    assert result.action == "removed"
    assert not wt.exists()


def test_merge_to_head_close_preserves_dirty_worktree(
    tmp_git_repo: Path,
) -> None:
    h = create_worktree(
        host_repo_path=tmp_git_repo,
        strategy=BranchStrategy.merge_to_head(),
    )
    (h.worktree_path / "uncommitted.txt").write_text("dirt")
    result = h.close()
    assert result.action == "preserved"
    assert result.reason == "dirty"
    assert h.worktree_path.exists()


def test_named_strategy_creates_branch(tmp_git_repo: Path) -> None:
    h = create_worktree(
        host_repo_path=tmp_git_repo,
        strategy=BranchStrategy.named("feat/x"),
    )
    try:
        assert h.branch == "feat/x"
        assert _branch_of(tmp_git_repo, h.worktree_path) == "feat/x"
    finally:
        h.close()


def test_named_strategy_rejects_existing_branch(tmp_git_repo: Path) -> None:
    subprocess.run(
        ["git", "branch", "feat/exists"],
        cwd=str(tmp_git_repo),
        check=True,
        capture_output=True,
    )
    with pytest.raises(BranchExists) as excinfo:
        create_worktree(
            host_repo_path=tmp_git_repo,
            strategy=BranchStrategy.named("feat/exists"),
        )
    assert excinfo.value.branch == "feat/exists"


def test_named_with_custom_base(tmp_git_repo: Path) -> None:
    subprocess.run(
        ["git", "checkout", "-b", "develop"],
        cwd=str(tmp_git_repo),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "checkout", "main"],
        cwd=str(tmp_git_repo),
        check=True,
        capture_output=True,
    )
    h = create_worktree(
        host_repo_path=tmp_git_repo,
        strategy=BranchStrategy.named("feat/y", base="develop"),
    )
    try:
        assert h.branch == "feat/y"
    finally:
        h.close()


def test_named_reuse_returns_existing_worktree(tmp_git_repo: Path) -> None:
    """throw_on_duplicate_worktree=False reuses the existing on-disk worktree."""
    first = create_worktree(
        host_repo_path=tmp_git_repo,
        strategy=BranchStrategy.named("feat/reuse"),
    )
    try:
        first_path = first.worktree_path
        assert first.managed is True
    finally:
        # Drop the lock but keep the worktree on disk by writing an
        # uncommitted file so close() preserves rather than removes it.
        (first.worktree_path / "uncommitted.txt").write_text("x")
        result = first.close()
        assert result.action == "preserved"

    second = create_worktree(
        host_repo_path=tmp_git_repo,
        strategy=BranchStrategy.named("feat/reuse"),
        throw_on_duplicate_worktree=False,
    )
    try:
        assert second.branch == "feat/reuse"
        assert second.worktree_path == first_path
        # Reused worktree is unmanaged — close() does NOT remove it.
        assert second.managed is False
    finally:
        result = second.close()
        assert result.action == "released_only"
    # Worktree survives close on reuse path.
    assert first_path.exists()


def test_named_reuse_default_true_still_raises(tmp_git_repo: Path) -> None:
    """Without throw_on_duplicate_worktree=False, the second call still raises."""
    first = create_worktree(
        host_repo_path=tmp_git_repo,
        strategy=BranchStrategy.named("feat/no-reuse"),
    )
    try:
        (first.worktree_path / "uncommitted.txt").write_text("x")
    finally:
        first.close()

    with pytest.raises(BranchExists) as excinfo:
        create_worktree(
            host_repo_path=tmp_git_repo,
            strategy=BranchStrategy.named("feat/no-reuse"),
        )
    assert excinfo.value.branch == "feat/no-reuse"


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
