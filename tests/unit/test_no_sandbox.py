"""Verify the no_sandbox provider."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from eden.providers._types import BranchStrategy, CreateOptions
from eden.sandboxes.no_sandbox import provider

pytestmark = pytest.mark.unit


def test_provider_metadata() -> None:
    p = provider()
    assert p.name == "no_sandbox"
    assert p.kind == "bind_mount"
    assert p.supports_strategy(BranchStrategy.head()) is True
    assert p.supports_strategy(BranchStrategy.merge_to_head()) is True
    assert p.supports_strategy(BranchStrategy.named("x")) is True


def test_handle_exec_runs_in_worktree(tmp_path: Path) -> None:
    p = provider()
    handle = p.create(
        CreateOptions(
            branch="main",
            worktree_path=tmp_path,
            host_repo_path=tmp_path,
            env={},
            mounts=(),
            name_hint=None,
        )
    )
    try:
        result = handle.exec(f'"{sys.executable}" -c "import os; print(os.getcwd())"')
        assert result.exit_code == 0
        assert str(tmp_path) in result.stdout
    finally:
        handle.close()


def test_handle_exec_explicit_cwd_overrides(tmp_path: Path) -> None:
    sub = tmp_path / "sub"
    sub.mkdir()
    p = provider()
    handle = p.create(
        CreateOptions(
            branch="main",
            worktree_path=tmp_path,
            host_repo_path=tmp_path,
            env={},
            mounts=(),
            name_hint=None,
        )
    )
    try:
        result = handle.exec(
            f'"{sys.executable}" -c "import os; print(os.getcwd())"',
            cwd=sub,
        )
        assert str(sub) in result.stdout
    finally:
        handle.close()


def test_handle_copy_in_and_out(tmp_path: Path) -> None:
    src = tmp_path / "a.txt"
    src.write_text("body")
    dst = tmp_path / "b.txt"
    handle = provider().create(
        CreateOptions(
            branch="main",
            worktree_path=tmp_path,
            host_repo_path=tmp_path,
            env={},
            mounts=(),
            name_hint=None,
        )
    )
    try:
        handle.copy_file_in(src, dst)
        assert dst.read_text() == "body"
        out = tmp_path / "c.txt"
        handle.copy_file_out(dst, out)
        assert out.read_text() == "body"
    finally:
        handle.close()


def test_handle_close_is_noop(tmp_path: Path) -> None:
    handle = provider().create(
        CreateOptions(
            branch="main",
            worktree_path=tmp_path,
            host_repo_path=tmp_path,
            env={},
            mounts=(),
            name_hint=None,
        )
    )
    handle.close()
    handle.close()  # idempotent
