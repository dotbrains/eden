"""Verify BranchStrategy factory methods and frozen-dataclass semantics."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from eden.providers._types import (
    BranchStrategy,
    CreateOptions,
    ExecResult,
    Mount,
)

pytestmark = pytest.mark.unit


def test_head_strategy() -> None:
    s = BranchStrategy.head()
    assert s.tag == "head"
    assert s.branch is None
    assert s.base == "main"


def test_merge_to_head_default_base() -> None:
    s = BranchStrategy.merge_to_head()
    assert s.tag == "merge_to_head"
    assert s.branch is None
    assert s.base == "main"


def test_merge_to_head_custom_base() -> None:
    s = BranchStrategy.merge_to_head(base="develop")
    assert s.base == "develop"


def test_named_strategy() -> None:
    s = BranchStrategy.named("feat/x")
    assert s.tag == "named"
    assert s.branch == "feat/x"
    assert s.base == "main"


def test_named_with_custom_base() -> None:
    s = BranchStrategy.named("feat/x", base="develop")
    assert s.base == "develop"


def test_branch_strategy_is_frozen() -> None:
    s = BranchStrategy.head()
    with pytest.raises(FrozenInstanceError):
        s.tag = "named"  # type: ignore[misc]


def test_mount_defaults_to_read_write() -> None:
    m = Mount(host=Path("/h"), sandbox=Path("/s"))
    assert m.read_only is False


def test_mount_read_only() -> None:
    m = Mount(host=Path("/h"), sandbox=Path("/s"), read_only=True)
    assert m.read_only is True


def test_mount_is_frozen() -> None:
    m = Mount(host=Path("/h"), sandbox=Path("/s"))
    with pytest.raises(FrozenInstanceError):
        m.read_only = True  # type: ignore[misc]


def test_exec_result_ok_property() -> None:
    assert ExecResult(stdout="", stderr="", exit_code=0).ok is True
    assert ExecResult(stdout="", stderr="", exit_code=1).ok is False


def test_exec_result_check_passes_on_zero() -> None:
    r = ExecResult(stdout="hi", stderr="", exit_code=0)
    assert r.check() is r


def test_exec_result_check_raises_on_nonzero() -> None:
    from eden.sandboxes.errors import ExecFailed

    r = ExecResult(stdout="", stderr="bad", exit_code=2)
    with pytest.raises(ExecFailed) as excinfo:
        r.check()
    assert excinfo.value.result is r


def test_create_options_holds_fields() -> None:
    opts = CreateOptions(
        branch="feat/x",
        worktree_path=Path("/wt"),
        host_repo_path=Path("/host"),
        env={"K": "V"},
        mounts=(Mount(host=Path("/a"), sandbox=Path("/b")),),
        name_hint="hint",
    )
    assert opts.branch == "feat/x"
    assert opts.env == {"K": "V"}
    assert len(opts.mounts) == 1


def test_create_options_is_frozen() -> None:
    opts = CreateOptions(
        branch="feat/x",
        worktree_path=Path("/wt"),
        host_repo_path=Path("/host"),
        env={},
        mounts=(),
        name_hint=None,
    )
    with pytest.raises(FrozenInstanceError):
        opts.branch = "other"  # type: ignore[misc]
