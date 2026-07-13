"""Verify StreamEvent dataclass + TextDeltaBuffer."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from eden.streaming import StreamEvent, TextDeltaBuffer

pytestmark = pytest.mark.unit


def test_stream_event_text_kind() -> None:
    ev = StreamEvent(
        type="text",
        agent_name="simulated",
        iteration=0,
        timestamp=datetime(2026, 5, 1, tzinfo=UTC),
        text="hello",
    )
    assert ev.type == "text"
    assert ev.text == "hello"
    assert ev.minutes_idle is None


def test_stream_event_idle_warning_kind() -> None:
    ev = StreamEvent(
        type="idle_warning",
        agent_name="simulated",
        iteration=0,
        timestamp=datetime(2026, 5, 1, tzinfo=UTC),
        minutes_idle=2,
    )
    assert ev.minutes_idle == 2
    assert ev.text is None


def test_buffer_emits_complete_lines_only() -> None:
    buf = TextDeltaBuffer()
    assert buf.feed("hello") == []
    assert buf.feed(" world\nsec") == ["hello world"]
    assert buf.feed("ond\n") == ["second"]


def test_buffer_handles_multiple_lines_in_one_chunk() -> None:
    buf = TextDeltaBuffer()
    assert buf.feed("a\nb\nc\n") == ["a", "b", "c"]


def test_buffer_flush_returns_residual() -> None:
    buf = TextDeltaBuffer()
    buf.feed("residual")
    assert buf.flush() == "residual"
    assert buf.flush() == ""


def test_stream_event_is_frozen() -> None:
    ev = StreamEvent(
        type="text",
        agent_name="simulated",
        iteration=0,
        timestamp=datetime(2026, 5, 1, tzinfo=UTC),
        text="hi",
    )
    with pytest.raises(FrozenInstanceError):
        ev.iteration = 99  # type: ignore[misc]


def test_stream_event_rejects_text_kind_without_text_payload() -> None:
    with pytest.raises(ValueError, match="text"):
        StreamEvent(
            type="text",
            agent_name="simulated",
            iteration=0,
            timestamp=datetime(2026, 5, 1, tzinfo=UTC),
        )


def test_stream_event_rejects_idle_warning_kind_without_minutes_idle_payload() -> None:
    with pytest.raises(ValueError, match="minutes_idle"):
        StreamEvent(
            type="idle_warning",
            agent_name="simulated",
            iteration=0,
            timestamp=datetime(2026, 5, 1, tzinfo=UTC),
        )
