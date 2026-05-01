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
    assert len(lines) == 3


def test_file_sink_creates_parent_dirs(tmp_path: Path) -> None:
    log_path = tmp_path / "deep" / "nest" / "out.log"
    sink = FileLogSink.open(log_path, level="info", env_values=())
    sink.close()
    assert log_path.exists()


def test_file_sink_close_is_idempotent(tmp_path: Path) -> None:
    sink = FileLogSink.open(tmp_path / "x.log", level="info", env_values=())
    sink.close()
    sink.close()  # must not raise
