"""Verify the opencode JSONL line parser."""

from __future__ import annotations

import json

import pytest

from eden.agents.opencode._stream import parse_line
from eden.streaming import StreamEvent

pytestmark = pytest.mark.unit


def _parse(payload: dict[str, object]) -> StreamEvent | None:
    return parse_line(json.dumps(payload), agent_name="opencode", iteration=5)


def test_returns_none_for_non_json_line() -> None:
    assert parse_line("not json", agent_name="opencode", iteration=0) is None
    assert parse_line("", agent_name="opencode", iteration=0) is None


def test_returns_none_for_unknown_event_type() -> None:
    assert _parse({"type": "heartbeat"}) is None


def test_step_start_emits_session_id() -> None:
    ev = _parse({"type": "step_start", "sessionID": "sess-abc"})
    assert ev is not None
    assert ev.type == "session_id"
    assert ev.session_id == "sess-abc"
    assert ev.iteration == 5
    assert ev.agent_name == "opencode"


def test_step_start_without_session_id_returns_none() -> None:
    assert _parse({"type": "step_start"}) is None
    assert _parse({"type": "step_start", "sessionID": ""}) is None
    assert _parse({"type": "step_start", "sessionID": 42}) is None


def test_text_event_emits_text() -> None:
    ev = _parse({"type": "text", "part": {"type": "text", "text": "hello"}})
    assert ev is not None
    assert ev.type == "text"
    assert ev.text == "hello"


def test_text_event_missing_part_returns_none() -> None:
    assert _parse({"type": "text"}) is None


def test_text_event_wrong_part_type_returns_none() -> None:
    assert _parse({"type": "text", "part": {"type": "other", "text": "x"}}) is None


def test_tool_use_completed_emits_tool_call() -> None:
    ev = _parse(
        {
            "type": "tool_use",
            "part": {
                "type": "tool",
                "tool": "Bash",
                "state": {
                    "status": "completed",
                    "input": {"command": "ls -la"},
                },
            },
        }
    )
    assert ev is not None
    assert ev.type == "tool_call"
    assert ev.tool_name == "Bash"
    assert ev.tool_input == {"command": "ls -la"}


def test_tool_use_pending_returns_none() -> None:
    # Mirror upstream: only emit completed tool calls.
    assert (
        _parse(
            {
                "type": "tool_use",
                "part": {
                    "type": "tool",
                    "tool": "Bash",
                    "state": {"status": "pending", "input": {"command": "x"}},
                },
            }
        )
        is None
    )


def test_tool_use_non_tool_part_returns_none() -> None:
    assert _parse({"type": "tool_use", "part": {"type": "text", "text": "x"}}) is None


def test_tool_use_missing_input_returns_none() -> None:
    assert (
        _parse(
            {
                "type": "tool_use",
                "part": {
                    "type": "tool",
                    "tool": "Bash",
                    "state": {"status": "completed"},
                },
            }
        )
        is None
    )


def test_error_string_emits_text() -> None:
    ev = _parse({"type": "error", "error": "rate limited"})
    assert ev is not None
    assert ev.type == "text"
    assert ev.text == "rate limited"


def test_error_object_message_emits_text() -> None:
    ev = _parse({"type": "error", "error": {"message": "boom"}})
    assert ev is not None
    assert ev.text == "boom"


def test_error_without_payload_returns_none() -> None:
    assert _parse({"type": "error"}) is None
