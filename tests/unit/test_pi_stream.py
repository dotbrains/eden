"""Verify the pi JSONL line parser."""

from __future__ import annotations

import json

import pytest

from eden.agents.pi._stream import parse_line
from eden.streaming import StreamEvent

pytestmark = pytest.mark.unit


def _parse(payload: dict[str, object]) -> StreamEvent | None:
    return parse_line(json.dumps(payload), agent_name="pi", iteration=2)


def test_returns_none_for_non_json_line() -> None:
    assert parse_line("not json", agent_name="pi", iteration=0) is None
    assert parse_line("", agent_name="pi", iteration=0) is None


def test_text_delta_emits_text() -> None:
    ev = _parse(
        {
            "type": "message_update",
            "assistantMessageEvent": {"type": "text_delta", "delta": "hi"},
        }
    )
    assert ev is not None
    assert ev.type == "text"
    assert ev.text == "hi"
    assert ev.agent_name == "pi"
    assert ev.iteration == 2


def test_message_update_without_text_delta_ignored() -> None:
    assert (
        _parse(
            {
                "type": "message_update",
                "assistantMessageEvent": {"type": "other", "delta": "x"},
            }
        )
        is None
    )
    assert _parse({"type": "message_update"}) is None


def test_tool_execution_start_known_tool_emits_tool_call() -> None:
    ev = _parse(
        {
            "type": "tool_execution_start",
            "toolName": "Bash",
            "args": {"command": "echo hello"},
        }
    )
    assert ev is not None
    assert ev.type == "tool_call"
    assert ev.tool_name == "Bash"
    assert ev.tool_input == {"command": "echo hello"}


def test_tool_execution_start_websearch_emits_tool_call() -> None:
    ev = _parse(
        {
            "type": "tool_execution_start",
            "toolName": "WebSearch",
            "args": {"query": "python typing"},
        }
    )
    assert ev is not None
    assert ev.tool_input == {"query": "python typing"}


def test_tool_execution_start_unknown_tool_ignored() -> None:
    assert (
        _parse(
            {
                "type": "tool_execution_start",
                "toolName": "InternalToolNotInTable",
                "args": {"foo": "bar"},
            }
        )
        is None
    )


def test_tool_execution_start_missing_required_arg_field_ignored() -> None:
    assert (
        _parse({"type": "tool_execution_start", "toolName": "Bash", "args": {"other": "x"}}) is None
    )


def test_error_emits_text() -> None:
    ev = _parse({"type": "error", "error": "kaboom"})
    assert ev is not None
    assert ev.type == "text"
    assert ev.text == "kaboom"


def test_agent_error_emits_text() -> None:
    ev = _parse({"type": "agent_error", "error": {"message": "timeout"}})
    assert ev is not None
    assert ev.text == "timeout"


def test_agent_end_emits_last_assistant_text() -> None:
    ev = _parse(
        {
            "type": "agent_end",
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": "go"}]},
                {
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": "step 1. "},
                        {"type": "text", "text": "step 2."},
                    ],
                },
            ],
        }
    )
    assert ev is not None
    assert ev.type == "text"
    assert ev.text == "step 1. step 2."


def test_agent_end_skips_trailing_user_messages() -> None:
    ev = _parse(
        {
            "type": "agent_end",
            "messages": [
                {"role": "assistant", "content": [{"type": "text", "text": "first"}]},
                {"role": "user", "content": [{"type": "text", "text": "later"}]},
            ],
        }
    )
    assert ev is None


def test_agent_end_assistant_without_text_returns_none() -> None:
    ev = _parse(
        {
            "type": "agent_end",
            "messages": [
                {"role": "assistant", "content": [{"type": "tool_use", "name": "x"}]},
            ],
        }
    )
    assert ev is None
