"""Verify Logging dataclass, default-path generation, and FileLogSink."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from eden.logging import Logging
from eden.logging._file import FileLogSink, default_log_path
from eden.streaming import StreamEvent

pytestmark = pytest.mark.unit


def _ts() -> datetime:
    return datetime(2026, 5, 1, 12, 0, 0, tzinfo=UTC)


def test_logging_file_factory(tmp_path: Path) -> None:
    cfg = Logging.file(tmp_path / "out.log")
    assert cfg.type == "file"
    assert cfg.path == tmp_path / "out.log"
    assert cfg.level == "info"


def test_logging_file_factory_with_level(tmp_path: Path) -> None:
    cfg = Logging.file(tmp_path / "out.log", level="debug")
    assert cfg.level == "debug"


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


def test_file_sink_writes_redacted_text(tmp_path: Path) -> None:
    log_path = tmp_path / "x.log"
    sink = FileLogSink.open(log_path, level="info", env_values=("mySecret",))
    try:
        ev = StreamEvent(
            type="text",
            agent_name="sim",
            iteration=0,
            timestamp=_ts(),
            text="password=mySecret here",
        )
        sink.write(ev)
    finally:
        sink.close()
    body = log_path.read_text()
    assert "mySecret" not in body
    assert "<redacted>" in body


def test_file_sink_writes_idle_warning(tmp_path: Path) -> None:
    log_path = tmp_path / "x.log"
    sink = FileLogSink.open(log_path, level="info", env_values=())
    try:
        ev = StreamEvent(
            type="idle_warning", agent_name="sim", iteration=1, timestamp=_ts(), minutes_idle=3
        )
        sink.write(ev)
    finally:
        sink.close()
    body = log_path.read_text()
    assert "idle_warning:" in body
    assert "minutes_idle=3" in body


def test_file_sink_appends_newlines(tmp_path: Path) -> None:
    log_path = tmp_path / "x.log"
    sink = FileLogSink.open(log_path, level="info", env_values=())
    try:
        for i in range(3):
            sink.write(
                StreamEvent(
                    type="text", agent_name="sim", iteration=i, timestamp=_ts(), text=f"line{i}"
                )
            )
    finally:
        sink.close()
    lines = log_path.read_text().splitlines()
    # First line is the "--- Run started: ... ---" delimiter; then 3 events.
    assert len(lines) == 4
    assert lines[0].startswith("--- Run started: ")
    assert lines[1:] == [
        "2026-05-01T12:00:00Z info [0] text: line0",
        "2026-05-01T12:00:00Z info [1] text: line1",
        "2026-05-01T12:00:00Z info [2] text: line2",
    ]


def test_file_sink_writes_run_started_delimiter(tmp_path: Path) -> None:
    log_path = tmp_path / "x.log"
    sink = FileLogSink.open(log_path, level="info", env_values=())
    sink.close()
    body = log_path.read_text()
    assert body.startswith("--- Run started: ")
    assert "T" in body  # ISO-8601 datetime
    assert body.rstrip().endswith("---")


def test_file_sink_appends_delimiter_per_run(tmp_path: Path) -> None:
    """Each ``open()`` of the same path appends a fresh delimiter."""
    log_path = tmp_path / "x.log"
    s1 = FileLogSink.open(log_path, level="info", env_values=())
    s1.close()
    s2 = FileLogSink.open(log_path, level="info", env_values=())
    s2.close()
    delimiters = [
        line for line in log_path.read_text().splitlines() if line.startswith("--- Run started: ")
    ]
    assert len(delimiters) == 2


def test_file_sink_creates_parent_dirs(tmp_path: Path) -> None:
    log_path = tmp_path / "deep" / "nest" / "out.log"
    sink = FileLogSink.open(log_path, level="info", env_values=())
    sink.close()
    assert log_path.exists()


def test_file_sink_close_is_idempotent(tmp_path: Path) -> None:
    sink = FileLogSink.open(tmp_path / "x.log", level="info", env_values=())
    sink.close()
    sink.close()  # must not raise


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
