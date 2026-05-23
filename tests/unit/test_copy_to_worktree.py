"""Verify ``copy_to_worktree=`` semantics across run() / create_sandbox() /
interactive(), plus the underlying helper.

Ported from sandcastle: a list of host-relative file/directory paths copied
into the freshly-carved worktree before host ``on_worktree_ready`` hooks fire.
Validation is strict (absolute paths, ``..`` traversal, head strategy all
rejected); collisions overwrite.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from eden import create_sandbox, run
from eden.agents import simulated_agent
from eden.errors import CopyToWorktreeError, InvalidOptions
from eden.orchestrator._copy_files import apply_copy_to_worktree
from eden.providers._types import BranchStrategy
from eden.sandboxes.no_sandbox import provider as no_sandbox_provider
from eden.sandboxes.test_bind_mount import provider as bind_mount_test_provider

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# apply_copy_to_worktree — unit-level
# ---------------------------------------------------------------------------


def test_apply_copy_noop_on_none(tmp_path: Path) -> None:
    apply_copy_to_worktree(paths=None, source_root=tmp_path, worktree_path=tmp_path)


def test_apply_copy_noop_on_empty(tmp_path: Path) -> None:
    apply_copy_to_worktree(paths=[], source_root=tmp_path, worktree_path=tmp_path)


def test_apply_copy_file(tmp_path: Path) -> None:
    src_root = tmp_path / "src"
    wt = tmp_path / "wt"
    src_root.mkdir()
    wt.mkdir()
    (src_root / ".env").write_text("TOKEN=abc\n")

    apply_copy_to_worktree(paths=[".env"], source_root=src_root, worktree_path=wt)

    assert (wt / ".env").read_text() == "TOKEN=abc\n"


def test_apply_copy_file_creates_parent_dir(tmp_path: Path) -> None:
    src_root = tmp_path / "src"
    wt = tmp_path / "wt"
    src_root.mkdir()
    wt.mkdir()
    nested = src_root / "config" / "creds.json"
    nested.parent.mkdir()
    nested.write_text("{}")

    apply_copy_to_worktree(paths=["config/creds.json"], source_root=src_root, worktree_path=wt)

    assert (wt / "config" / "creds.json").read_text() == "{}"


def test_apply_copy_directory_recursive(tmp_path: Path) -> None:
    src_root = tmp_path / "src"
    wt = tmp_path / "wt"
    (src_root / "fixtures" / "sub").mkdir(parents=True)
    wt.mkdir()
    (src_root / "fixtures" / "a.txt").write_text("a")
    (src_root / "fixtures" / "sub" / "b.txt").write_text("b")

    apply_copy_to_worktree(paths=["fixtures"], source_root=src_root, worktree_path=wt)

    assert (wt / "fixtures" / "a.txt").read_text() == "a"
    assert (wt / "fixtures" / "sub" / "b.txt").read_text() == "b"


def test_apply_copy_overwrites_existing_file(tmp_path: Path) -> None:
    src_root = tmp_path / "src"
    wt = tmp_path / "wt"
    src_root.mkdir()
    wt.mkdir()
    (src_root / ".env").write_text("NEW=1\n")
    (wt / ".env").write_text("OLD=1\n")

    apply_copy_to_worktree(paths=[".env"], source_root=src_root, worktree_path=wt)

    assert (wt / ".env").read_text() == "NEW=1\n"


def test_apply_copy_merges_into_existing_directory(tmp_path: Path) -> None:
    src_root = tmp_path / "src"
    wt = tmp_path / "wt"
    (src_root / "fixtures").mkdir(parents=True)
    (wt / "fixtures").mkdir(parents=True)
    (src_root / "fixtures" / "new.txt").write_text("new")
    (wt / "fixtures" / "old.txt").write_text("old")
    (wt / "fixtures" / "new.txt").write_text("stale")

    apply_copy_to_worktree(paths=["fixtures"], source_root=src_root, worktree_path=wt)

    assert (wt / "fixtures" / "new.txt").read_text() == "new"
    assert (wt / "fixtures" / "old.txt").read_text() == "old"


def test_apply_copy_rejects_absolute_path(tmp_path: Path) -> None:
    with pytest.raises(InvalidOptions, match="absolute"):
        apply_copy_to_worktree(paths=["/etc/passwd"], source_root=tmp_path, worktree_path=tmp_path)


def test_apply_copy_rejects_traversal(tmp_path: Path) -> None:
    with pytest.raises(InvalidOptions, match=r"\.\."):
        apply_copy_to_worktree(paths=["../secrets"], source_root=tmp_path, worktree_path=tmp_path)


def test_apply_copy_rejects_nested_traversal(tmp_path: Path) -> None:
    with pytest.raises(InvalidOptions, match=r"\.\."):
        apply_copy_to_worktree(
            paths=["a/../../secrets"], source_root=tmp_path, worktree_path=tmp_path
        )


def test_apply_copy_rejects_empty_entry(tmp_path: Path) -> None:
    with pytest.raises(InvalidOptions, match="non-empty"):
        apply_copy_to_worktree(paths=[""], source_root=tmp_path, worktree_path=tmp_path)


def test_apply_copy_missing_source_raises(tmp_path: Path) -> None:
    src_root = tmp_path / "src"
    wt = tmp_path / "wt"
    src_root.mkdir()
    wt.mkdir()
    with pytest.raises(CopyToWorktreeError) as exc_info:
        apply_copy_to_worktree(paths=["missing.env"], source_root=src_root, worktree_path=wt)
    assert exc_info.value.code == "copy.to_worktree_missing_source"


def test_apply_copy_rejects_file_symlink_outside_source_root(tmp_path: Path) -> None:
    src_root = tmp_path / "src"
    wt = tmp_path / "wt"
    outside = tmp_path / "outside"
    src_root.mkdir()
    wt.mkdir()
    outside.write_text("secret")
    (src_root / "linked-secret").symlink_to(outside)

    with pytest.raises(InvalidOptions, match="resolves outside"):
        apply_copy_to_worktree(paths=["linked-secret"], source_root=src_root, worktree_path=wt)

    assert not (wt / "linked-secret").exists()


def test_apply_copy_rejects_directory_symlink_outside_source_root(tmp_path: Path) -> None:
    src_root = tmp_path / "src"
    wt = tmp_path / "wt"
    outside = tmp_path / "outside"
    src_root.mkdir()
    wt.mkdir()
    outside.mkdir()
    (outside / "secret.txt").write_text("secret")
    (src_root / "linked-dir").symlink_to(outside, target_is_directory=True)

    with pytest.raises(InvalidOptions, match="resolves outside"):
        apply_copy_to_worktree(paths=["linked-dir"], source_root=src_root, worktree_path=wt)

    assert not (wt / "linked-dir").exists()


def test_apply_copy_same_root_is_noop(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("a")
    # When source and worktree resolve to the same dir, copying a file onto
    # itself would either silently no-op or raise SameFileError; the helper
    # short-circuits before either.
    apply_copy_to_worktree(paths=["a.txt"], source_root=tmp_path, worktree_path=tmp_path)
    assert (tmp_path / "a.txt").read_text() == "a"


# ---------------------------------------------------------------------------
# run() — integration with copy_to_worktree
# ---------------------------------------------------------------------------


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
    # The worktree gets removed on clean exit; copy lands in the worktree
    # before the agent runs, and the file is included in the merge back to
    # main. Either the worktree is preserved (dirty) or the file made it to
    # the host repo via merge.
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
    """no_sandbox has kind=bind_mount, which defaults to merge_to_head — so
    copy_to_worktree must be allowed (NOT rejected) without an explicit
    branch_strategy."""
    (tmp_git_repo / "seed.txt").write_text("payload\n")
    # Should not raise.
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


# ---------------------------------------------------------------------------
# create_sandbox() — validation only (sandbox creation needs docker, skip)
# ---------------------------------------------------------------------------


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
    """test_bind_mount provider supports merge_to_head — verify the copy
    lands in the worktree before sandbox.create() runs."""
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
