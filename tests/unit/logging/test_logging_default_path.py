"""Verify default log path generation."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from eden.logging._file import default_log_path

pytestmark = pytest.mark.unit


def _ts() -> datetime:
    return datetime(2026, 5, 1, 12, 0, 0, tzinfo=UTC)


def test_default_log_path_sanitizes_branch(tmp_path: Path) -> None:
    p = default_log_path(host_repo_path=tmp_path, branch="eden/feat/x", now=_ts())
    assert p.parent == tmp_path / ".eden" / "logs"
    assert p.name.startswith("eden-feat-x-")
    assert p.name.endswith(".log")


def test_default_log_path_truncates(tmp_path: Path) -> None:
    long_branch = "x" * 200
    p = default_log_path(host_repo_path=tmp_path, branch=long_branch, now=_ts())
    # filename: <sanitized 64 chars>-<utc>.log
    stem = p.stem
    sanitized = stem.rsplit("-", 1)[0]
    assert len(sanitized) <= 64


def test_default_log_path_empty_branch_fallback(tmp_path: Path) -> None:
    p = default_log_path(host_repo_path=tmp_path, branch="///", now=_ts())
    stem = p.stem
    sanitized = stem.rsplit("-", 1)[0]
    assert sanitized == "run"


def test_default_log_path_strips_windows_unsafe_chars(tmp_path: Path) -> None:
    p = default_log_path(host_repo_path=tmp_path, branch='feat:deploy"x*', now=_ts())
    # All Windows-illegal chars (`:`, `"`, `*`) replaced with `-`. Adjacent
    # illegal chars collapse to a single dash.
    stem = p.stem
    sanitized = stem.rsplit("-", 1)[0]
    for c in ':"*<>?|':
        assert c not in sanitized


def test_default_log_path_includes_target_branch_and_name(tmp_path: Path) -> None:
    p = default_log_path(
        host_repo_path=tmp_path,
        target_branch="main",
        branch="eden/20260501-abc",
        name="Review #42",
        now=_ts(),
    )
    assert p.name.startswith("main-eden-20260501-abc-Review-42-")


def test_default_log_path_truncates_prefix_before_run_name(tmp_path: Path) -> None:
    p = default_log_path(
        host_repo_path=tmp_path,
        target_branch="main",
        branch="eden/" + ("x" * 120),
        name="review issue 123",
        now=_ts(),
    )
    sanitized = p.stem.rsplit("-", 1)[0]
    assert len(sanitized) <= 64
    assert sanitized.endswith("review-issue-123")
