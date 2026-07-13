"""Worktree collision state-detection tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from eden.worktree._git import list_worktrees
from eden.worktree._state import IN_PROGRESS_MARKERS, detect_in_progress, parse_worktree_list

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
    records = parse_worktree_list(porcelain)
    assert len(records) == 3
    assert records[0].path == Path("/repo")
    assert records[0].branch == "main"
    assert records[1].branch == "eden/feature-x"
    assert records[2].branch is None  # detached


def test_parse_worktree_list_handles_missing_trailing_blank() -> None:
    porcelain = "worktree /repo\nbranch refs/heads/main\n"
    records = parse_worktree_list(porcelain)
    assert len(records) == 1
    assert records[0].branch == "main"


def test_parse_worktree_list_empty() -> None:
    assert parse_worktree_list("") == ()


def test_list_worktrees_returns_main_after_init(tmp_git_repo: Path) -> None:
    records = list_worktrees(repo_path=tmp_git_repo)
    assert len(records) == 1
    assert records[0].branch == "main"


def test_detect_in_progress_returns_none_on_clean_repo(tmp_git_repo: Path) -> None:
    assert detect_in_progress(repo_path=tmp_git_repo) is None


def test_detect_in_progress_finds_rebase_merge(tmp_git_repo: Path) -> None:
    marker = tmp_git_repo / ".git" / "rebase-merge"
    marker.mkdir()
    found = detect_in_progress(repo_path=tmp_git_repo)
    assert found is not None
    assert found.name == "rebase-merge"


def test_detect_in_progress_finds_merge_head(tmp_git_repo: Path) -> None:
    marker = tmp_git_repo / ".git" / "MERGE_HEAD"
    marker.write_text("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n")
    found = detect_in_progress(repo_path=tmp_git_repo)
    assert found is not None
    assert found.name == "MERGE_HEAD"


def test_detect_in_progress_covers_all_markers() -> None:
    """Pin the set of in-progress markers we care about."""
    assert "rebase-merge" in IN_PROGRESS_MARKERS
    assert "rebase-apply" in IN_PROGRESS_MARKERS
    assert "MERGE_HEAD" in IN_PROGRESS_MARKERS
    assert "CHERRY_PICK_HEAD" in IN_PROGRESS_MARKERS


def test_detect_in_progress_resolves_gitdir_pointer(tmp_git_repo: Path) -> None:
    """When .git is a file (worktree-style), follow the gitdir: pointer."""
    wt_path = tmp_git_repo / "wt"
    subprocess.run(
        ["git", "worktree", "add", "-b", "feature-x", str(wt_path)],
        cwd=tmp_git_repo,
        check=True,
        capture_output=True,
    )
    pointer = (wt_path / ".git").read_text(encoding="utf-8").strip()
    assert pointer.startswith("gitdir: ")
    real_gitdir = Path(pointer[len("gitdir: ") :])
    (real_gitdir / "MERGE_HEAD").write_text("ref\n")
    try:
        found = detect_in_progress(repo_path=wt_path)
        assert found is not None
        assert found.name == "MERGE_HEAD"
    finally:
        (real_gitdir / "MERGE_HEAD").unlink()
