"""Verify ``copy_to_worktree=`` run() and create_sandbox() semantics."""

from __future__ import annotations

from pathlib import Path

import pytest

from eden import create_sandbox, run
from eden.agents import simulated_agent
from eden.errors import CopyToWorktreeError, InvalidOptions
from eden.providers._types import BranchStrategy
from eden.sandboxes.no_sandbox import provider as no_sandbox_provider
from eden.sandboxes.test_bind_mount import provider as bind_mount_test_provider

pytestmark = pytest.mark.unit


def test_run_copies_files_into_worktree(tmp_git_repo: Path) -> None:
    (tmp_git_repo / "seed.txt").write_text("seed-payload\n")

    result = run(
        agent=simulated_agent(output="hi\n<promise>COMPLETE</promise>\n"),
        sandbox=no_sandbox_provider(),
        prompt="seed test",
        cwd=tmp_git_repo,
        branch_strategy=BranchStrategy.merge_to_head(base="main"),
        copy_to_worktree=["seed.txt"],
    )

    expected = (result.preserved_worktree_path or result.worktree_path) / "seed.txt"
    if expected.exists():
        assert expected.read_text() == "seed-payload\n"
    else:
        assert (tmp_git_repo / "seed.txt").read_text() == "seed-payload\n"


def test_run_rejects_copy_with_head_strategy(tmp_git_repo: Path) -> None:
    (tmp_git_repo / "seed.txt").write_text("x")
    with pytest.raises(InvalidOptions, match="head"):
        run(
            agent=simulated_agent(output="<promise>COMPLETE</promise>\n"),
            sandbox=no_sandbox_provider(),
            prompt="x",
            cwd=tmp_git_repo,
            branch_strategy=BranchStrategy.head(),
            copy_to_worktree=["seed.txt"],
        )


def test_run_default_strategy_with_no_sandbox_allows_copy(
    tmp_git_repo: Path,
) -> None:
    (tmp_git_repo / "seed.txt").write_text("payload\n")
    result = run(
        agent=simulated_agent(output="<promise>COMPLETE</promise>\n"),
        sandbox=no_sandbox_provider(),
        prompt="x",
        cwd=tmp_git_repo,
        copy_to_worktree=["seed.txt"],
    )
    assert result.completion_signal == "<promise>COMPLETE</promise>"


def test_run_missing_copy_source_raises(tmp_git_repo: Path) -> None:
    with pytest.raises(CopyToWorktreeError):
        run(
            agent=simulated_agent(output="<promise>COMPLETE</promise>\n"),
            sandbox=no_sandbox_provider(),
            prompt="x",
            cwd=tmp_git_repo,
            branch_strategy=BranchStrategy.merge_to_head(base="main"),
            copy_to_worktree=["nonexistent.txt"],
        )


def test_create_sandbox_rejects_copy_with_head_strategy(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_git_repo)
    with pytest.raises(InvalidOptions, match="head"):
        create_sandbox(
            sandbox=no_sandbox_provider(),
            branch_strategy=BranchStrategy.head(),
            copy_to_worktree=[".env"],
        )


def test_create_sandbox_copies_files_with_merge_to_head(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_git_repo)
    (tmp_git_repo / "seed.txt").write_text("seed\n")

    sb = create_sandbox(
        sandbox=bind_mount_test_provider(),
        branch_strategy=BranchStrategy.merge_to_head(base="main"),
        copy_to_worktree=["seed.txt"],
    )
    try:
        assert (sb.worktree.worktree_path / "seed.txt").read_text() == "seed\n"
    finally:
        sb.close()


def test_create_sandbox_missing_copy_source_raises(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_git_repo)
    with pytest.raises(CopyToWorktreeError):
        create_sandbox(
            sandbox=bind_mount_test_provider(),
            branch_strategy=BranchStrategy.merge_to_head(base="main"),
            copy_to_worktree=["nonexistent.txt"],
        )
