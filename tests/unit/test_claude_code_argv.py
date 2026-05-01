"""Verify the Claude Code argv builder."""

from __future__ import annotations

import pytest

from eden.agents.claude_code._argv import build_argv

pytestmark = pytest.mark.unit


def test_minimal_argv() -> None:
    argv = build_argv(model="claude-opus-4-7", effort=None, prompt="hi", extra_args=())
    assert argv == [
        "claude",
        "--print",
        "--output-format",
        "stream-json",
        "--verbose",
        "--model",
        "claude-opus-4-7",
        "--",
        "hi",
    ]


def test_effort_threaded() -> None:
    argv = build_argv(model="m", effort="high", prompt="p", extra_args=())
    assert "--thinking-effort" in argv
    idx = argv.index("--thinking-effort")
    assert argv[idx + 1] == "high"


def test_extra_args_appended_before_double_dash() -> None:
    argv = build_argv(
        model="m",
        effort=None,
        prompt="p",
        extra_args=("--allowed-tools", "Read,Write"),
    )
    dd = argv.index("--")
    assert argv[dd + 1] == "p"
    assert "Read,Write" in argv
    assert argv.index("Read,Write") < dd


def test_prompt_with_metacharacters_passed_unescaped() -> None:
    """The prompt is a positional argv element; subprocess does no shell parsing."""
    argv = build_argv(model="m", effort=None, prompt="echo $PWD; rm -rf /", extra_args=())
    assert argv[-1] == "echo $PWD; rm -rf /"


def test_default_argv_does_not_include_thinking_effort() -> None:
    argv = build_argv(model="m", effort=None, prompt="p", extra_args=())
    assert "--thinking-effort" not in argv
