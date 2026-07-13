"""Unit tests for the verbose ``raw`` StreamEvent."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from eden.logging._config import Logging
from eden.logging._format import format_line
from eden.streaming import StreamEvent

pytestmark = pytest.mark.unit


def _ts() -> datetime:
    return datetime(2026, 1, 1, tzinfo=UTC)


def test_raw_event_requires_text() -> None:
    with pytest.raises(ValueError, match='type="raw" requires text'):
        StreamEvent(type="raw", agent_name="a", iteration=0, timestamp=_ts())


def test_raw_event_constructs_with_text() -> None:
    ev = StreamEvent(type="raw", agent_name="a", iteration=0, timestamp=_ts(), text="{json}")
    assert ev.type == "raw"
    assert ev.text == "{json}"


def test_format_line_renders_raw_verbatim() -> None:
    ev = StreamEvent(type="raw", agent_name="a", iteration=3, timestamp=_ts(), text='{"x":1}')
    line = format_line(ev, level="info")
    assert line.endswith('raw: {"x":1}')


def test_logging_verbose_defaults_false() -> None:
    assert Logging.file("/tmp/x.log").verbose is False
    assert Logging.stdout().verbose is False


def test_logging_verbose_opt_in() -> None:
    assert Logging.file("/tmp/x.log", verbose=True).verbose is True
    assert Logging.stdout(verbose=True).verbose is True
