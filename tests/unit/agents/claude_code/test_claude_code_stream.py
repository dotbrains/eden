"""Verify parse_line maps stream-json shapes to StreamEvent kinds."""

from __future__ import annotations

import json

import pytest

from eden.agents.claude_code._stream import parse_line
from eden.streaming import StreamEvent

pytestmark = pytest.mark.unit


def _parse(obj: dict[str, object]) -> StreamEvent | None:
    return parse_line(json.dumps(obj), agent_name="claude-code", iteration=0)


def test_system_init_returns_none() -> None:
    assert _parse({"type": "system", "subtype": "init"}) is None


def test_assistant_text_block_returns_text_event() -> None:
    ev = _parse(
        {
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": "hello world"}]},
        }
    )
    assert ev is not None
    assert ev.type == "text"
    assert ev.text == "hello world"


def test_assistant_tool_use_block_returns_tool_call() -> None:
    ev = _parse(
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "tool_use", "name": "Read", "input": {"path": "/x"}},
                ],
            },
        }
    )
    assert ev is not None
    assert ev.type == "tool_call"
    assert ev.tool_name == "Read"
    assert ev.tool_input == {"path": "/x"}


def test_assistant_thinking_block_returns_none() -> None:
    assert (
        _parse(
            {
                "type": "assistant",
                "message": {"content": [{"type": "thinking", "thinking": "..."}]},
            }
        )
        is None
    )


def test_user_tool_result_returns_none() -> None:
    assert (
        _parse(
            {
                "type": "user",
                "message": {"content": [{"type": "tool_result", "content": "..."}]},
            }
        )
        is None
    )


def test_result_returns_usage_event() -> None:
    ev = _parse(
        {
            "type": "result",
            "session_id": "abc-123",
            "usage": {
                "input_tokens": 10,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
                "output_tokens": 20,
            },
        }
    )
    assert ev is not None
    assert ev.type == "usage"
    assert ev.session_id == "abc-123"
    assert ev.usage is not None
    assert ev.usage.input_tokens == 10
    assert ev.usage.output_tokens == 20


def test_malformed_json_returns_none() -> None:
    assert parse_line("not json {", agent_name="claude-code", iteration=0) is None


def test_assistant_multi_block_returns_first_text_only() -> None:
    """When an assistant message has multiple content blocks, we surface the
    first text block (subsequent blocks would arrive as future stream-json
    lines from Claude Code in practice)."""
    ev = _parse(
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "text", "text": "first"},
                    {"type": "text", "text": "second"},
                ],
            },
        }
    )
    assert ev is not None
    assert ev.text == "first"


def test_unknown_top_level_type_returns_none() -> None:
    assert _parse({"type": "future_kind"}) is None


def test_result_without_usage_returns_none() -> None:
    """A result line missing the usage field is treated as unparseable
    (Claude Code always includes usage; if missing, drop the line)."""
    assert _parse({"type": "result", "session_id": "x"}) is None
