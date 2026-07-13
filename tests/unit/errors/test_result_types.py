"""Verify shared result dataclasses (RunResult, Iteration, Usage, Commit, Timeouts)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from eden._types import Commit, Iteration, RunResult, Timeouts, Usage

pytestmark = pytest.mark.unit


def test_iteration_is_frozen() -> None:
    it = Iteration(
        index=0, completion_signal=None, session_id=None, session_file_path=None, usage=None
    )
    with pytest.raises(FrozenInstanceError):
        it.index = 1  # type: ignore[misc]


def test_usage_is_frozen() -> None:
    u = Usage(
        input_tokens=1, cache_creation_input_tokens=2, cache_read_input_tokens=3, output_tokens=4
    )
    with pytest.raises(FrozenInstanceError):
        u.input_tokens = 99  # type: ignore[misc]


def test_commit_carries_sha() -> None:
    c = Commit(sha="abc123")
    assert c.sha == "abc123"


def test_timeouts_defaults() -> None:
    t = Timeouts()
    assert t.hook_step == 60.0
    assert t.iteration_step is None


def test_run_result_defaults_for_3a_deferred_fields() -> None:
    rr = RunResult(
        iterations=[],
        completion_signal=None,
        branch="HEAD",
        stdout="",
        commits=[],
        worktree_path=Path("/tmp/x"),
        preserved_worktree_path=None,
        merged_to_target_branch=None,
        cwd=Path("/tmp/x"),
        prompt="",
        env={},
        log_file_path=None,
        session_id=None,
        session_file_path=None,
        usage=None,
    )
    assert rr.commits == []
    assert rr.merged_to_target_branch is None
    assert rr.session_id is None
    assert rr.usage is None


def test_run_result_is_frozen() -> None:
    rr = RunResult(
        iterations=[],
        completion_signal=None,
        branch="b",
        stdout="",
        commits=[],
        worktree_path=Path("/x"),
        preserved_worktree_path=None,
        merged_to_target_branch=None,
        cwd=Path("/x"),
        prompt="",
        env={},
        log_file_path=None,
        session_id=None,
        session_file_path=None,
        usage=None,
    )
    with pytest.raises(FrozenInstanceError):
        rr.branch = "other"  # type: ignore[misc]


def test_commit_is_frozen() -> None:
    c = Commit(sha="abc123")
    with pytest.raises(FrozenInstanceError):
        c.sha = "def456"  # type: ignore[misc]


def test_timeouts_is_frozen() -> None:
    t = Timeouts()
    with pytest.raises(FrozenInstanceError):
        t.hook_step = 120.0  # type: ignore[misc]
