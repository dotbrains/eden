"""Verify the codex JSONL line parser."""

from __future__ import annotations

import json

import pytest

from eden.agents.codex._stream import parse_line
from eden.streaming import StreamEvent

pytestmark = pytest.mark.unit


def _parse(payload: dict[str, object]) -> StreamEvent | None:
    return parse_line(json.dumps(payload), agent_name="codex", iteration=3)


def test_returns_none_for_non_json_line() -> None:
    assert parse_line("not json", agent_name="codex", iteration=0) is None
    assert parse_line("", agent_name="codex", iteration=0) is None


def test_returns_none_for_malformed_json() -> None:
    assert parse_line("{not json}", agent_name="codex", iteration=0) is None


def test_returns_none_for_unknown_event_type() -> None:
    assert _parse({"type": "heartbeat"}) is None


def test_thread_started_emits_session_id() -> None:
    ev = _parse({"type": "thread.started", "thread_id": "abc123"})
    assert ev is not None
    assert ev.type == "session_id"
    assert ev.session_id == "abc123"
    assert ev.iteration == 3
    assert ev.agent_name == "codex"


def test_thread_started_without_thread_id_returns_none() -> None:
    assert _parse({"type": "thread.started"}) is None
    assert _parse({"type": "thread.started", "thread_id": ""}) is None
    assert _parse({"type": "thread.started", "thread_id": 42}) is None


def test_agent_message_emits_text() -> None:
    ev = _parse(
        {
            "type": "item.completed",
            "item": {"type": "agent_message", "text": "hello world"},
        }
    )
    assert ev is not None
    assert ev.type == "text"
    assert ev.text == "hello world"


def test_item_completed_non_agent_message_ignored() -> None:
    assert _parse({"type": "item.completed", "item": {"type": "other", "text": "x"}}) is None


def test_command_execution_emits_tool_call() -> None:
    ev = _parse(
        {
            "type": "item.started",
            "item": {"type": "command_execution", "command": "ls -la"},
        }
    )
    assert ev is not None
    assert ev.type == "tool_call"
    assert ev.tool_name == "Bash"
    assert ev.tool_input == {"command": "ls -la"}


def test_item_started_non_command_execution_ignored() -> None:
    assert _parse({"type": "item.started", "item": {"type": "reasoning", "command": "x"}}) is None


def test_error_string_emits_text() -> None:
    ev = _parse({"type": "error", "error": "boom"})
    assert ev is not None
    assert ev.type == "text"
    assert ev.text == "boom"


def test_error_object_with_message_emits_text() -> None:
    ev = _parse({"type": "error", "error": {"message": "rate limited"}})
    assert ev is not None
    assert ev.text == "rate limited"


def test_error_top_level_message_emits_text() -> None:
    ev = _parse({"type": "error", "message": "auth missing"})
    assert ev is not None
    assert ev.text == "auth missing"


def test_error_without_payload_returns_none() -> None:
    assert _parse({"type": "error"}) is None


def test_turn_completed_emits_usage_with_cache_split() -> None:
    ev = _parse(
        {
            "type": "turn.completed",
            "usage": {
                "input_tokens": 1000,
                "cached_input_tokens": 400,
                "output_tokens": 250,
            },
        }
    )
    assert ev is not None
    assert ev.type == "usage"
    assert ev.usage is not None
    # input_tokens is total - cached so the accounting matches Claude's split
    assert ev.usage.input_tokens == 600
    assert ev.usage.cache_read_input_tokens == 400
    assert ev.usage.cache_creation_input_tokens == 0
    assert ev.usage.output_tokens == 250


def test_turn_completed_without_usage_returns_none() -> None:
    assert _parse({"type": "turn.completed"}) is None


def test_turn_completed_with_partial_usage_returns_none() -> None:
    # Missing output_tokens — return None rather than fabricate a 0
    assert (
        _parse(
            {
                "type": "turn.completed",
                "usage": {"input_tokens": 10, "cached_input_tokens": 0},
            }
        )
        is None
    )


def test_turn_completed_with_non_int_usage_returns_none() -> None:
    assert (
        _parse(
            {
                "type": "turn.completed",
                "usage": {
                    "input_tokens": "ten",
                    "cached_input_tokens": 0,
                    "output_tokens": 5,
                },
            }
        )
        is None
    )
