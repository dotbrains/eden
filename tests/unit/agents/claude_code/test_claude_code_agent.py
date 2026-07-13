"""Verify the claude_code() factory produces an Agent that satisfies the Protocol."""

from __future__ import annotations

import json

import pytest

from eden.agents import Agent, claude_code
from tests.unit.agents.claude_code._helpers import _ctx

pytestmark = pytest.mark.unit


def test_default_metadata() -> None:
    a = claude_code(model="claude-opus-4-8")
    assert a.name == "claude-code"
    assert a.model == "claude-opus-4-8"
    assert isinstance(a, Agent)


def test_model_defaults_to_opus_4_8() -> None:
    """No model arg picks the latest stable Opus."""
    a = claude_code()
    assert a.model == "claude-opus-4-8"


def test_explicit_model_overrides_default() -> None:
    a = claude_code(model="claude-sonnet-4-6")
    assert a.model == "claude-sonnet-4-6"


def test_custom_name() -> None:
    a = claude_code(model="m", name="my-agent")
    assert a.name == "my-agent"


def test_captures_sessions_default_true() -> None:
    a = claude_code(model="m")
    assert a.captures_sessions is True


def test_captures_sessions_false_overrides() -> None:
    a = claude_code(model="m", capture_sessions=False)
    assert a.captures_sessions is False


def test_build_command_returns_argv_with_stdin_sigil() -> None:
    a = claude_code(model="m")
    argv = a.build_command(_ctx(prompt="hi"))
    assert argv[0] == "claude"
    assert "stream-json" in argv
    # Prompt is delivered via stdin (`-p -`), not appended to argv.
    assert argv[-2:] == ["-p", "-"]
    assert "hi" not in argv


def test_stdin_content_returns_prompt() -> None:
    a = claude_code(model="m")
    assert hasattr(a, "stdin_content")
    payload = a.stdin_content(_ctx(prompt="my-prompt"))
    assert payload == "my-prompt"


def test_build_command_with_effort_includes_thinking_effort() -> None:
    a = claude_code(model="m", effort="high")
    argv = a.build_command(_ctx())
    assert "--thinking-effort" in argv


def test_parse_stream_returns_text_for_assistant_block() -> None:
    a = claude_code(model="m")
    line = json.dumps(
        {
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": "hi"}]},
        }
    )
    ev = a.parse_stream(line)
    assert ev is not None
    assert ev.type == "text"
    assert ev.text == "hi"
    assert ev.agent_name == "claude-code"


def test_parse_stream_returns_none_for_system() -> None:
    a = claude_code(model="m")
    assert a.parse_stream(json.dumps({"type": "system", "subtype": "init"})) is None
