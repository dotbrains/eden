"""Verify log line formatter."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from eden.logging._format import format_line
from eden.streaming import StreamEvent

pytestmark = pytest.mark.unit


def _ts() -> datetime:
    return datetime(2026, 5, 1, 12, 34, 56, tzinfo=UTC)


def test_format_text_event() -> None:
    ev = StreamEvent(
        type="text", agent_name="sim", iteration=0, timestamp=_ts(), text="hello world"
    )
    line = format_line(ev, level="info")
    assert line.startswith("2026-05-01T12:34:56Z info [0] text:")
    assert line.endswith("hello world")


def test_format_idle_warning_event() -> None:
    ev = StreamEvent(
        type="idle_warning", agent_name="sim", iteration=2, timestamp=_ts(), minutes_idle=4
    )
    line = format_line(ev, level="warn")
    assert "warn [2] idle_warning:" in line
    assert "minutes_idle=4" in line


def test_format_strips_trailing_newline_in_text() -> None:
    ev = StreamEvent(type="text", agent_name="sim", iteration=0, timestamp=_ts(), text="line\n")
    line = format_line(ev, level="info")
    assert line.endswith("line")
