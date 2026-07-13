"""Verify the top-level create_sandbox factory."""

from __future__ import annotations

from pathlib import Path

import pytest

from eden.providers._types import (
    BranchStrategy,
    Mount,
)
from eden.sandboxes import create_sandbox
from eden.sandboxes.errors import UnsupportedStrategy
from tests.unit.create_sandbox.create_sandbox_helpers import StubProvider

pytestmark = pytest.mark.unit


def test_branch_and_branch_strategy_are_mutually_exclusive(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_git_repo)
    p = StubProvider()
    with pytest.raises(ValueError):
        create_sandbox(
            sandbox=p,
            branch="x",
            branch_strategy=BranchStrategy.head(),
        )


def test_branch_arg_translates_to_named_strategy(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_git_repo)
    p = StubProvider()
    s = create_sandbox(sandbox=p, branch="feat/x")
    try:
        assert s.worktree.branch == "feat/x"
    finally:
        s.close()


def test_default_strategy_for_bind_mount_is_merge_to_head(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_git_repo)
    p = StubProvider(kind="bind_mount")
    s = create_sandbox(sandbox=p)
    try:
        assert s.worktree.branch.startswith("eden/")
        assert s.worktree.managed is True
    finally:
        s.close()


def test_default_strategy_for_none_is_head(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_git_repo)
    p = StubProvider(kind="none")
    s = create_sandbox(sandbox=p)
    try:
        assert s.worktree.branch == "HEAD"
        assert s.worktree.managed is False
    finally:
        s.close()


def test_unsupported_strategy_raises(tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_git_repo)
    p = StubProvider(supported=frozenset({"merge_to_head"}))
    with pytest.raises(UnsupportedStrategy):
        create_sandbox(sandbox=p, branch_strategy=BranchStrategy.head())


def test_passes_env_and_mounts_to_provider(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_git_repo)
    p = StubProvider()
    mount = Mount(host=tmp_git_repo, sandbox=Path("/data"))
    s = create_sandbox(
        sandbox=p,
        env={"K": "V"},
        mounts=(mount,),
        name="my-feature",
    )
    try:
        opts = p.seen_opts[0]
        assert opts.env == {"K": "V"}
        assert opts.mounts == (mount,)
        assert opts.name_hint == "my-feature"
    finally:
        s.close()


def test_create_sandbox_loads_dot_eden_env(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    eden_dir = tmp_git_repo / ".eden"
    eden_dir.mkdir()
    (eden_dir / ".env").write_text("FROM_FILE=value\n")
    monkeypatch.chdir(tmp_git_repo)
    p = StubProvider()
    s = create_sandbox(sandbox=p, env={"EXPLICIT": "override"})
    try:
        opts = p.seen_opts[0]
        assert opts.env == {"FROM_FILE": "value", "EXPLICIT": "override"}
    finally:
        s.close()


def test_create_sandbox_explicit_env_overrides_dot_env(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    eden_dir = tmp_git_repo / ".eden"
    eden_dir.mkdir()
    (eden_dir / ".env").write_text("KEY=from_file\n")
    monkeypatch.chdir(tmp_git_repo)
    p = StubProvider()
    s = create_sandbox(sandbox=p, env={"KEY": "from_caller"})
    try:
        assert p.seen_opts[0].env == {"KEY": "from_caller"}
    finally:
        s.close()


def test_git_setup_timeout_threads_to_worktree(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from eden._types import Timeouts

    monkeypatch.chdir(tmp_git_repo)
    p = StubProvider()
    s = create_sandbox(sandbox=p, timeouts=Timeouts(git_setup=3.5))
    try:
        assert s.worktree._git_timeout == 3.5
    finally:
        s.close()


def test_git_setup_timeout_defaults_to_60s(
    tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_git_repo)
    p = StubProvider()
    s = create_sandbox(sandbox=p)
    try:
        assert s.worktree._git_timeout == 60.0
    finally:
        s.close()
