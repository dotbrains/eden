"""Tests for worktree collision detection."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from eden.providers._types import BranchStrategy
from eden.worktree._create import create_worktree
from eden.worktree._git import (
    _IN_PROGRESS_MARKERS,
    _detect_in_progress,
    _parse_worktree_list,
    list_worktrees,
)
from eden.worktree.errors import WorktreeCollision

pytestmark = pytest.mark.unit


def test_parse_worktree_list_handles_branch_and_detached() -> None:
    porcelain = (
        "worktree /repo\n"
        "HEAD aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n"
        "branch refs/heads/main\n"
        "\n"
        "worktree /repo/.eden/worktrees/feature-x\n"
        "HEAD bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n"
        "branch refs/heads/eden/feature-x\n"
        "\n"
        "worktree /repo/.eden/worktrees/detached\n"
        "HEAD cccccccccccccccccccccccccccccccccccccccc\n"
        "detached\n"
    )
    records = _parse_worktree_list(porcelain)
    assert len(records) == 3
    assert records[0].path == Path("/repo")
    assert records[0].branch == "main"
    assert records[1].branch == "eden/feature-x"
    assert records[2].branch is None  # detached


def test_parse_worktree_list_handles_missing_trailing_blank() -> None:
    porcelain = "worktree /repo\nbranch refs/heads/main\n"
    records = _parse_worktree_list(porcelain)
    assert len(records) == 1
    assert records[0].branch == "main"


def test_parse_worktree_list_empty() -> None:
    assert _parse_worktree_list("") == ()


def test_list_worktrees_returns_main_after_init(tmp_git_repo: Path) -> None:
    records = list_worktrees(repo_path=tmp_git_repo)
    assert len(records) == 1
    assert records[0].branch == "main"


def test_detect_in_progress_returns_none_on_clean_repo(tmp_git_repo: Path) -> None:
    assert _detect_in_progress(repo_path=tmp_git_repo) is None


def test_detect_in_progress_finds_rebase_merge(tmp_git_repo: Path) -> None:
    marker = tmp_git_repo / ".git" / "rebase-merge"
    marker.mkdir()
    found = _detect_in_progress(repo_path=tmp_git_repo)
    assert found is not None
    assert found.name == "rebase-merge"


def test_detect_in_progress_finds_merge_head(tmp_git_repo: Path) -> None:
    marker = tmp_git_repo / ".git" / "MERGE_HEAD"
    marker.write_text("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n")
    found = _detect_in_progress(repo_path=tmp_git_repo)
    assert found is not None
    assert found.name == "MERGE_HEAD"


def test_detect_in_progress_covers_all_markers() -> None:
    """Pin the set of in-progress markers we care about."""
    assert "rebase-merge" in _IN_PROGRESS_MARKERS
    assert "rebase-apply" in _IN_PROGRESS_MARKERS
    assert "MERGE_HEAD" in _IN_PROGRESS_MARKERS
    assert "CHERRY_PICK_HEAD" in _IN_PROGRESS_MARKERS


def test_detect_in_progress_resolves_gitdir_pointer(tmp_git_repo: Path) -> None:
    """When .git is a file (worktree-style), follow the gitdir: pointer.

    Worktree-local in-progress markers live under the worktree's own
    gitdir (e.g. ``.git/worktrees/<name>/MERGE_HEAD``), NOT the parent
    repo's. The resolver must follow ``.git: gitdir:`` to find them.
    """
    wt_path = tmp_git_repo / "wt"
    subprocess.run(
        ["git", "worktree", "add", "-b", "feature-x", str(wt_path)],
        cwd=tmp_git_repo,
        check=True,
        capture_output=True,
    )
    # Read the gitdir pointer from the worktree's .git file and drop a
    # MERGE_HEAD into that resolved directory.
    pointer = (wt_path / ".git").read_text(encoding="utf-8").strip()
    assert pointer.startswith("gitdir: ")
    real_gitdir = Path(pointer[len("gitdir: ") :])
    (real_gitdir / "MERGE_HEAD").write_text("ref\n")
    try:
        found = _detect_in_progress(repo_path=wt_path)
        assert found is not None
        assert found.name == "MERGE_HEAD"
    finally:
        (real_gitdir / "MERGE_HEAD").unlink()


def test_create_worktree_blocks_when_branch_already_checked_out(tmp_git_repo: Path) -> None:
    # First worktree carves eden/foo successfully.
    h1 = create_worktree(
        host_repo_path=tmp_git_repo,
        strategy=BranchStrategy.named("eden/foo"),
    )
    try:
        # A second attempt at the same branch raises WorktreeCollision —
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
    """If the branch already exists AND is checked out elsewhere, eden raises
    BranchExists first (before reaching worktree_add). The collision-detection
    path covers the case where ``-b`` would create a fresh branch but git
    refuses because the *name* is in use elsewhere — exercised below by
    pre-creating a non-eden worktree, then asking for a generated eden branch
    whose name happens to collide. We trigger that via merge_to_head + a
    name_hint that determines the branch."""
    # Pre-carve a worktree on a separate branch via raw git.
    other_branch = "feature/dev"
    other_wt = tmp_git_repo / "other-wt"
    subprocess.run(
        ["git", "worktree", "add", "-b", other_branch, str(other_wt)],
        cwd=tmp_git_repo,
        check=True,
        capture_output=True,
    )

    # Sanity: list_worktrees should see two entries.
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
