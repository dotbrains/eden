"""Verify the Claude Code argv builder."""

from __future__ import annotations

import pytest

from eden.agents.claude_code._argv import build_argv

pytestmark = pytest.mark.unit


def test_minimal_argv() -> None:
    argv = build_argv(model="claude-opus-4-7", effort=None, extra_args=())
    assert argv == [
        "claude",
        "--print",
        "--output-format",
        "stream-json",
        "--verbose",
        "--model",
        "claude-opus-4-7",
        "-p",
        "-",
    ]


def test_argv_uses_stdin_sigil_for_prompt() -> None:
    """``-p -`` tells claude to read the prompt from stdin (avoids 128 KB execve cap)."""
    argv = build_argv(model="m", effort=None, extra_args=())
    assert argv[-2:] == ["-p", "-"]


def test_effort_threaded() -> None:
    argv = build_argv(model="m", effort="high", extra_args=())
    assert "--thinking-effort" in argv
    idx = argv.index("--thinking-effort")
    assert argv[idx + 1] == "high"


def test_extra_args_appended_before_stdin_sigil() -> None:
    argv = build_argv(
        model="m",
        effort=None,
        extra_args=("--allowed-tools", "Read,Write"),
    )
    p_idx = argv.index("-p")
    assert "Read,Write" in argv
    assert argv.index("Read,Write") < p_idx


def test_default_argv_does_not_include_thinking_effort() -> None:
    argv = build_argv(model="m", effort=None, extra_args=())
    assert "--thinking-effort" not in argv


def test_resume_session_appends_resume_flag() -> None:
    argv = build_argv(model="m", effort=None, extra_args=(), resume_session="abc-123")
    assert "--resume" in argv
    idx = argv.index("--resume")
    assert argv[idx + 1] == "abc-123"
    # Resume flag precedes extra_args + stdin sigil.
    assert idx < argv.index("-p")


def test_no_resume_session_omits_flag() -> None:
    argv = build_argv(model="m", effort=None, extra_args=(), resume_session=None)
    assert "--resume" not in argv


def test_permission_mode_omitted_by_default() -> None:
    argv = build_argv(model="m", effort=None, extra_args=())
    assert "--permission-mode" not in argv


def test_permission_mode_appends_flag() -> None:
    argv = build_argv(model="m", effort=None, extra_args=(), permission_mode="acceptEdits")
    assert "--permission-mode" in argv
    idx = argv.index("--permission-mode")
    assert argv[idx + 1] == "acceptEdits"
    # Mode flag precedes extra_args + stdin sigil.
    assert idx < argv.index("-p")


def test_permission_mode_appears_before_extra_args() -> None:
    argv = build_argv(
        model="m",
        effort=None,
        extra_args=("--allowed-tools", "Read"),
        permission_mode="plan",
    )
    assert argv.index("--permission-mode") < argv.index("--allowed-tools")
