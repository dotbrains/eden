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


def test_interactive_exec_runs_argv_with_inherited_stdio(tmp_path: Path) -> None:
    """``interactive_exec`` runs the argv with stdio inherited; returns exit code."""
    import sys

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
        rc = handle.interactive_exec(  # type: ignore[attr-defined]
            [sys.executable, "-c", "import sys; sys.exit(0)"],
        )
        assert rc == 0

        rc7 = handle.interactive_exec(  # type: ignore[attr-defined]
            [sys.executable, "-c", "import sys; sys.exit(7)"],
        )
        assert rc7 == 7
    finally:
        handle.close()


def test_interactive_exec_uses_provided_cwd(tmp_path: Path) -> None:
    """When cwd is given, the subprocess starts there."""
    import sys

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
    out = tmp_path / "where.txt"
    target = tmp_path / "subdir"
    target.mkdir()
    try:
        rc = handle.interactive_exec(  # type: ignore[attr-defined]
            [
                sys.executable,
                "-c",
                f"import os; open({str(out)!r}, 'w').write(os.getcwd())",
            ],
            cwd=target,
        )
        assert rc == 0
        # macOS may resolve symlinks under /private/var, so compare resolved paths.
        assert Path(out.read_text()).resolve() == target.resolve()
    finally:
        handle.close()
