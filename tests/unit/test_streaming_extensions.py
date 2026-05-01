"""Verify Phase 3b extensions to StreamEvent."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from eden._types import Usage
from eden.streaming import StreamEvent

pytestmark = pytest.mark.unit


def _ts() -> datetime:
    return datetime(2026, 5, 1, tzinfo=UTC)


def _u() -> Usage:
    return Usage(
        input_tokens=10,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=0,
        output_tokens=20,
    )


def test_tool_call_event_round_trip() -> None:
    ev = StreamEvent(
        type="tool_call",
        agent_name="claude-code",
        iteration=0,
        timestamp=_ts(),
        tool_name="Read",
        tool_input={"path": "/x"},
    )
    assert ev.tool_name == "Read"
    assert ev.tool_input == {"path": "/x"}
    assert ev.text is None


def test_tool_call_requires_tool_name() -> None:
    with pytest.raises(ValueError, match="tool_name"):
        StreamEvent(
            type="tool_call",
            agent_name="claude-code",
            iteration=0,
            timestamp=_ts(),
            tool_input={"path": "/x"},
        )


def test_usage_event_round_trip() -> None:
    ev = StreamEvent(
        type="usage",
        agent_name="claude-code",
        iteration=0,
        timestamp=_ts(),
        usage=_u(),
        session_id="abc-123",
    )
    assert ev.usage == _u()
    assert ev.session_id == "abc-123"


def test_usage_requires_usage_field() -> None:
    with pytest.raises(ValueError, match="usage"):
        StreamEvent(
            type="usage",
            agent_name="claude-code",
            iteration=0,
            timestamp=_ts(),
            session_id="abc-123",
        )


def test_text_event_still_works_after_extension() -> None:
    ev = StreamEvent(
        type="text",
        agent_name="claude-code",
        iteration=0,
        timestamp=_ts(),
        text="hello",
    )
    assert ev.tool_name is None
    assert ev.tool_input is None
    assert ev.usage is None
    assert ev.session_id is None
