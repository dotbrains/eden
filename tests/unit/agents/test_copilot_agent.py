"""Verify the copilot agent factory + argv shape + parser."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, cast

import pytest

from eden.agents import IterationContext
from eden.agents.copilot import copilot
from eden.errors import InvalidOptions
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


def test_copilot_default_metadata() -> None:
    a = copilot()
    assert a.name == "copilot"
    assert getattr(a, "captures_sessions", None) is False


def test_copilot_build_command_shape() -> None:
    a = copilot(model="claude-sonnet-4")
    argv = a.build_command(_ctx(prompt="hello"))
    assert argv[:3] == ["copilot", "-p", "hello"]
    assert "--output-format" in argv
    assert argv[argv.index("--output-format") + 1] == "json"
    assert "--model" in argv
    assert argv[argv.index("--model") + 1] == "claude-sonnet-4"


def test_copilot_effort_threads_flag() -> None:
    a = copilot(effort="high")
    argv = a.build_command(_ctx())
    assert "--effort" in argv
    assert argv[argv.index("--effort") + 1] == "high"


def test_copilot_no_effort_omits_flag() -> None:
    a = copilot()
    argv = a.build_command(_ctx())
    assert "--effort" not in argv


def test_copilot_allow_all_tools_appends_flag() -> None:
    a = copilot(allow_all_tools=True)
    argv = a.build_command(_ctx())
    assert "--allow-all-tools" in argv


def test_copilot_interactive_command_uses_interactive_prompt_flag() -> None:
    a = copilot(effort="high", allow_all_tools=True, extra_args=("--config", "x.yaml"))
    build_interactive = cast(Any, a).build_interactive_command
    argv = build_interactive(_ctx(prompt="seed"))
    assert argv[:3] == ["copilot", "--model", "claude-sonnet-4"]
    assert "-p" not in argv
    assert "--output-format" not in argv
    assert "--allow-all-tools" in argv
    assert argv[argv.index("--effort") + 1] == "high"
    assert argv[argv.index("-i") + 1] == "seed"
    assert argv.index("x.yaml") < argv.index("-i")


def test_copilot_prompt_too_long_raises() -> None:
    a = copilot()
    huge = "x" * 200_000
    with pytest.raises(InvalidOptions) as exc:
        a.build_command(_ctx(prompt=huge))
    assert exc.value.code == "config.prompt_too_long"


def test_copilot_parse_stream_text_delta() -> None:
    a = copilot()
    line = json.dumps({"type": "assistant.message_delta", "data": {"deltaContent": "hi"}})
    ev = a.parse_stream(line)
    assert ev is not None
    assert ev.type == "text"
    assert ev.text == "hi"


def test_copilot_parse_stream_tool_call_normalises_bash() -> None:
    a = copilot()
    line = json.dumps(
        {
            "type": "tool.execution_start",
            "data": {"toolName": "bash", "arguments": {"command": "ls"}},
        }
    )
    ev = a.parse_stream(line)
    assert ev is not None
    assert ev.type == "tool_call"
    # Lowercase "bash" → title-case "Bash" for parity with other agents.
    assert ev.tool_name == "Bash"
    assert ev.tool_input == {"command": "ls"}


def test_copilot_parse_stream_session_id_from_result() -> None:
    a = copilot()
    line = json.dumps({"type": "result", "sessionId": "abc"})
    ev = a.parse_stream(line)
    assert ev is not None
    assert ev.type == "session_id"
    assert ev.session_id == "abc"


def test_copilot_parse_stream_error_emits_text() -> None:
    a = copilot()
    line = json.dumps({"type": "error", "error": "boom"})
    ev = a.parse_stream(line)
    assert ev is not None
    assert ev.type == "text"
    assert ev.text == "boom"


def test_copilot_parse_stream_returns_none_for_garbage() -> None:
    a = copilot()
    assert a.parse_stream("not json") is None
    assert a.parse_stream("") is None
