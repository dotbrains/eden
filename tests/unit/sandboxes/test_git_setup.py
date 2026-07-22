"""Verify sandbox-side git setup helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from eden.providers._types import ExecResult
from eden.sandboxes._git_setup import configure_sandbox_git
from tests.unit.create_sandbox.create_sandbox_helpers import StubHandle

pytestmark = pytest.mark.unit


def test_git_setup_skips_normalized_existing_safe_directory(tmp_path: Path) -> None:
    handle = StubHandle(
        worktree_path=Path("/workspace"),
        exec_results=[
            ExecResult(stdout="C:\\repo\\worktree\n", stderr="", exit_code=0),
        ],
    )

    handle.worktree_path = Path("C:/repo/worktree")
    configure_sandbox_git(handle, tmp_path, timeout=3.0)

    assert [call["cmd"] for call in handle.exec_calls] == [
        "git config --global --get-all safe.directory || true"
    ]


def test_git_setup_adds_missing_safe_directory(tmp_path: Path) -> None:
    handle = StubHandle(
        worktree_path=Path("/workspace"),
        exec_results=[
            ExecResult(stdout="", stderr="", exit_code=0),
            ExecResult(stdout="", stderr="", exit_code=0),
        ],
    )

    configure_sandbox_git(handle, tmp_path, timeout=4.0)

    assert [call["cmd"] for call in handle.exec_calls] == [
        "git config --global --get-all safe.directory || true",
        "git config --global --add safe.directory /workspace",
    ]
    assert [call["timeout"] for call in handle.exec_calls] == [4.0, 4.0]


def test_git_setup_propagates_host_identity(tmp_git_repo: Path) -> None:
    handle = StubHandle(
        worktree_path=Path("/workspace"),
        exec_results=[
            ExecResult(stdout="", stderr="", exit_code=0),
            ExecResult(stdout="", stderr="", exit_code=0),
            ExecResult(stdout="", stderr="", exit_code=0),
            ExecResult(stdout="", stderr="", exit_code=0),
        ],
    )

    configure_sandbox_git(handle, tmp_git_repo, timeout=5.0)

    assert [call["cmd"] for call in handle.exec_calls] == [
        "git config --global --get-all safe.directory || true",
        "git config --global --add safe.directory /workspace",
        "git config --global user.name Test",
        "git config --global user.email test@example.com",
    ]


def test_git_setup_skips_missing_host_identity(tmp_path: Path) -> None:
    handle = StubHandle(
        worktree_path=Path("/workspace"),
        exec_results=[
            ExecResult(stdout="", stderr="", exit_code=0),
            ExecResult(stdout="", stderr="", exit_code=0),
        ],
    )

    configure_sandbox_git(handle, tmp_path, timeout=5.0)

    assert [call["cmd"] for call in handle.exec_calls] == [
        "git config --global --get-all safe.directory || true",
        "git config --global --add safe.directory /workspace",
    ]
