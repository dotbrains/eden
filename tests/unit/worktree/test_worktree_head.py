"""Verify create_worktree with the head strategy."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from eden.providers._types import BranchStrategy
from eden.worktree._create import (
    CloseResult,
    WorktreeHandle,
    create_worktree,
)
from eden.worktree.errors import DirtyHostBlocked, WorktreeLocked

pytestmark = pytest.mark.unit


def test_head_returns_unmanaged_handle_using_host_path(
    tmp_git_repo: Path,
) -> None:
    h = create_worktree(host_repo_path=tmp_git_repo, strategy=BranchStrategy.head())
    try:
        assert isinstance(h, WorktreeHandle)
        assert h.managed is False
        assert h.worktree_path == tmp_git_repo
        assert h.host_repo_path == tmp_git_repo
        assert h.branch == "HEAD"
    finally:
        h.close()


def test_head_blocks_on_dirty_host(tmp_git_repo: Path) -> None:
    (tmp_git_repo / "dirty.txt").write_text("uncommitted")
    with pytest.raises(DirtyHostBlocked) as excinfo:
        create_worktree(host_repo_path=tmp_git_repo, strategy=BranchStrategy.head())
    assert excinfo.value.host_repo_path == tmp_git_repo
    assert any("dirty.txt" in f for f in excinfo.value.dirty_files)


def test_head_close_returns_released_only(tmp_git_repo: Path) -> None:
    h = create_worktree(host_repo_path=tmp_git_repo, strategy=BranchStrategy.head())
    result = h.close()
    assert isinstance(result, CloseResult)
    assert result.action == "released_only"


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="msvcrt.locking is per-process; same-process re-acquire isn't blocked",
)
def test_head_lock_blocks_second_acquire(tmp_git_repo: Path) -> None:
    h = create_worktree(host_repo_path=tmp_git_repo, strategy=BranchStrategy.head())
    try:
        with pytest.raises(WorktreeLocked):
            create_worktree(host_repo_path=tmp_git_repo, strategy=BranchStrategy.head())
    finally:
        h.close()


def test_head_close_is_idempotent(tmp_git_repo: Path) -> None:
    h = create_worktree(host_repo_path=tmp_git_repo, strategy=BranchStrategy.head())
    r1 = h.close()
    r2 = h.close()
    assert r1.action == "released_only"
    assert r2.action == "released_only"


def test_head_supports_context_manager(tmp_git_repo: Path) -> None:
    with create_worktree(host_repo_path=tmp_git_repo, strategy=BranchStrategy.head()) as h:
        assert h.managed is False
