"""create_sandbox behavior with caller-owned worktrees and cleanup failures."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from eden.errors import InvalidOptions
from eden.orchestrator import create_worktree
from eden.providers._types import BranchStrategy, CreateOptions
from eden.sandboxes import create_sandbox
from eden.worktree._create import WorktreeHandle
from eden.worktree._create import create_worktree as carve_worktree
from tests.unit.create_sandbox.create_sandbox_helpers import StubProvider

pytestmark = pytest.mark.unit


def test_worktree_mutually_exclusive_with_branch_args(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_git_repo)
    p = StubProvider()
    with create_worktree() as wt:
        with pytest.raises(ValueError):
            create_sandbox(sandbox=p, worktree=wt, branch="x")
        with pytest.raises(ValueError):
            create_sandbox(sandbox=p, worktree=wt, branch_strategy=BranchStrategy.head())
        with pytest.raises(ValueError):
            create_sandbox(sandbox=p, worktree=wt, base_branch="main")


def test_caller_worktree_survives_sandbox_close(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Split ownership: Sandbox.close() tears down the container only."""
    monkeypatch.chdir(tmp_git_repo)
    p = StubProvider()
    wt = create_worktree()
    try:
        s = create_sandbox(sandbox=p, worktree=wt)
        assert s.owns_worktree is False
        assert s.worktree is wt
        handle = s.handle
        s.close()
        assert handle.closed[0] is True  # type: ignore[attr-defined]
        # Worktree is still on disk and still open; the caller owns it.
        assert wt.worktree_path.exists()
    finally:
        result = wt.close()
    # close() above is the FIRST close of the handle: a clean worktree is
    # removed, not reported as already-closed.
    assert result.action == "removed"


def test_one_worktree_hosts_sequential_sandboxes(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_git_repo)
    p = StubProvider()
    with create_worktree() as wt:
        with create_sandbox(sandbox=p, worktree=wt) as first:
            assert first.worktree.branch == wt.branch
        with create_sandbox(sandbox=p, worktree=wt) as second:
            assert second.worktree.branch == wt.branch
        assert len(p.seen_opts) == 2
        assert all(o.worktree_path == wt.worktree_path for o in p.seen_opts)


def test_provider_failure_leaves_caller_worktree_open(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    @dataclass
    class _ExplodingProvider(StubProvider):
        def create(self, opts: CreateOptions) -> Any:
            raise RuntimeError("boom")

    monkeypatch.chdir(tmp_git_repo)
    with create_worktree() as wt:
        with pytest.raises(RuntimeError):
            create_sandbox(sandbox=_ExplodingProvider(), worktree=wt)
        # The factory must not close a worktree it does not own.
        assert wt.worktree_path.exists()
        # Reusable after the failure.
        with create_sandbox(sandbox=StubProvider(), worktree=wt):
            pass


def test_copy_to_worktree_rejected_for_head_style_worktree(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_git_repo)
    # The head-style check fires before any copy happens, so the source file
    # need not exist (and the host tree must stay clean for the head carve).
    wt = carve_worktree(host_repo_path=tmp_git_repo, strategy=BranchStrategy.head())
    try:
        with pytest.raises(InvalidOptions):
            create_sandbox(
                sandbox=StubProvider(),
                worktree=wt,
                copy_to_worktree=["seed.txt"],
            )
    finally:
        wt.close()


def test_close_propagates_handle_error_over_worktree_error(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failing worktree.close() must not replace the handle's exception."""
    monkeypatch.chdir(tmp_git_repo)
    s = create_sandbox(sandbox=StubProvider())

    def _handle_boom() -> None:
        raise RuntimeError("handle boom")

    def _wt_boom(self: WorktreeHandle) -> None:
        raise OSError("worktree boom")

    monkeypatch.setattr(s.handle, "close", _handle_boom)
    monkeypatch.setattr(WorktreeHandle, "close", _wt_boom)
    try:
        with pytest.raises(RuntimeError, match="handle boom"):
            s.close()
    finally:
        monkeypatch.undo()
        s.worktree.close()


def test_create_failure_propagates_over_worktree_cleanup_error(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failing cleanup close() must not replace the provider's create error."""

    @dataclass
    class _ExplodingProvider(StubProvider):
        def create(self, opts: CreateOptions) -> Any:
            raise RuntimeError("create boom")

    monkeypatch.chdir(tmp_git_repo)
    real_close = WorktreeHandle.close
    carved: list[WorktreeHandle] = []

    def _capture_and_boom(self: WorktreeHandle) -> None:
        carved.append(self)
        raise OSError("worktree boom")

    monkeypatch.setattr(WorktreeHandle, "close", _capture_and_boom)
    try:
        with pytest.raises(RuntimeError, match="create boom"):
            create_sandbox(sandbox=_ExplodingProvider())
    finally:
        monkeypatch.undo()
        for wt in carved:
            real_close(wt)
