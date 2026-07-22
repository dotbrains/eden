"""Verify sandbox-side git setup helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from eden.providers._types import ExecResult
from eden.sandboxes._git_setup import ensure_git_safe_directory
from tests.unit.create_sandbox.create_sandbox_helpers import StubHandle

pytestmark = pytest.mark.unit


def test_safe_directory_setup_skips_normalized_existing_entry() -> None:
    handle = StubHandle(
        worktree_path=Path("/workspace"),
        exec_results=[
            ExecResult(stdout="C:\\repo\\worktree\n", stderr="", exit_code=0),
        ],
    )

    handle.worktree_path = Path("C:/repo/worktree")
    ensure_git_safe_directory(handle, timeout=3.0)

    assert [call["cmd"] for call in handle.exec_calls] == [
        "git config --global --get-all safe.directory || true"
    ]


def test_safe_directory_setup_adds_missing_entry() -> None:
    handle = StubHandle(
        worktree_path=Path("/workspace"),
        exec_results=[
            ExecResult(stdout="", stderr="", exit_code=0),
            ExecResult(stdout="", stderr="", exit_code=0),
        ],
    )

    ensure_git_safe_directory(handle, timeout=4.0)

    assert [call["cmd"] for call in handle.exec_calls] == [
        "git config --global --get-all safe.directory || true",
        "git config --global --add safe.directory /workspace",
    ]
    assert [call["timeout"] for call in handle.exec_calls] == [4.0, 4.0]
