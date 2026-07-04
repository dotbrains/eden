"""Verify the claude_code() factory produces an Agent that satisfies the Protocol."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from pathlib import Path

import pytest

from eden.agents import Agent, IterationContext, claude_code
from eden.providers._types import ExecResult

pytestmark = pytest.mark.unit


class _StubHandle:
    worktree_path = Path("/workspace")

    def exec(
        self,
        cmd: str,
        *,
        on_line: Callable[[str], None] | None = None,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
        stdin: str | None = None,
    ) -> ExecResult:
        return ExecResult(stdout="", stderr="", exit_code=0)

    def copy_file_in(self, host: Path, sandbox: Path) -> None: ...
    def copy_file_out(self, sandbox: Path, host: Path) -> None: ...
    def close(self) -> None: ...


def _ctx(prompt: str = "do work") -> IterationContext:
    return IterationContext(
        iteration=0,
        prompt=prompt,
        sandbox_handle=_StubHandle(),
        worktree_path=Path("/workspace"),
        branch="HEAD",
        name=None,
    )


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


def test_dangerously_skip_permissions_default_off() -> None:
    a = claude_code(model="m")
    argv = a.build_command(_ctx())
    assert "--dangerously-skip-permissions" not in argv


def test_dangerously_skip_permissions_appends_flag() -> None:
    a = claude_code(model="m", dangerously_skip_permissions=True)
    argv = a.build_command(_ctx())
    assert "--dangerously-skip-permissions" in argv
    # Flag must precede the prompt-stdin sigil.
    assert argv.index("--dangerously-skip-permissions") < argv.index("-p")


def test_dangerously_skip_permissions_propagates_to_interactive() -> None:
    a = claude_code(model="m", dangerously_skip_permissions=True)
    argv = a.build_interactive_command(_ctx(prompt=""))
    assert "--dangerously-skip-permissions" in argv


def test_permission_mode_default_off() -> None:
    a = claude_code(model="m")
    argv = a.build_command(_ctx())
    assert "--permission-mode" not in argv


def test_permission_mode_appends_flag() -> None:
    a = claude_code(model="m", permission_mode="acceptEdits")
    argv = a.build_command(_ctx())
    assert "--permission-mode" in argv
    assert argv[argv.index("--permission-mode") + 1] == "acceptEdits"
    assert argv.index("--permission-mode") < argv.index("-p")


def test_permission_mode_propagates_to_interactive() -> None:
    a = claude_code(model="m", permission_mode="plan")
    argv = a.build_interactive_command(_ctx(prompt=""))
    assert "--permission-mode" in argv
    assert argv[argv.index("--permission-mode") + 1] == "plan"


def test_permission_mode_invalid_value_raises() -> None:
    from eden.errors import InvalidOptions

    with pytest.raises(InvalidOptions, match="permission_mode"):
        claude_code(model="m", permission_mode="bogus")  # type: ignore[arg-type]


def test_permission_mode_conflicts_with_skip_permissions() -> None:
    from eden.errors import InvalidOptions

    with pytest.raises(InvalidOptions, match="at most one"):
        claude_code(
            model="m",
            permission_mode="acceptEdits",
            dangerously_skip_permissions=True,
        )


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
