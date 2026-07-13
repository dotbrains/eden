"""Verify the cursor agent factory + argv shape + parser."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from pathlib import Path

import pytest

from eden.agents import IterationContext
from eden.agents.cursor import cursor
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


def test_cursor_default_metadata() -> None:
    a = cursor()
    assert a.name == "cursor"
    # captures_sessions is False on _CursorAgent (a private dataclass);
    # asserting via getattr keeps the test off the public Agent Protocol's
    # surface, which intentionally doesn't declare the field.
    assert getattr(a, "captures_sessions", None) is False


def test_cursor_build_command_shape() -> None:
    a = cursor(model="some-model")
    argv = a.build_command(_ctx(prompt="hello"))
    assert argv[0] == "agent"
    assert "--print" in argv
    assert "--output-format" in argv
    assert argv[argv.index("--output-format") + 1] == "stream-json"
    assert "--model" in argv
    assert argv[argv.index("--model") + 1] == "some-model"
    # Prompt is positional (last).
    assert argv[-1] == "hello"


def test_cursor_force_appends_flag() -> None:
    a = cursor(force=True)
    argv = a.build_command(_ctx(prompt="p"))
    assert "--force" in argv
    assert argv.index("--force") < argv.index("p")


def test_cursor_force_default_off() -> None:
    a = cursor()
    argv = a.build_command(_ctx())
    assert "--force" not in argv


def test_cursor_extra_args_threaded() -> None:
    a = cursor(extra_args=("--verbose",))
    argv = a.build_command(_ctx(prompt="p"))
    assert "--verbose" in argv
    assert argv.index("--verbose") < argv.index("p")


def test_cursor_prompt_too_long_raises() -> None:
    a = cursor()
    huge = "x" * 200_000  # > 120 KB guard
    with pytest.raises(InvalidOptions) as exc:
        a.build_command(_ctx(prompt=huge))
    assert exc.value.code == "config.prompt_too_long"


def test_cursor_parse_stream_handles_tool_call() -> None:
    a = cursor()
    line = json.dumps({"type": "tool_call", "name": "Bash", "input": {"command": "ls"}})
    ev = a.parse_stream(line)
    assert ev is not None
    assert ev.type == "tool_call"
    assert ev.tool_name == "Bash"
    assert ev.tool_input == {"command": "ls"}


def test_cursor_parse_stream_delegates_to_claude_for_assistant_block() -> None:
    """Cursor's stream-json reuses Claude's `assistant` event shape."""
    a = cursor()
    line = json.dumps(
        {
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": "hello"}]},
        }
    )
    ev = a.parse_stream(line)
    assert ev is not None
    assert ev.type == "text"
    assert ev.text == "hello"


def test_cursor_parse_stream_returns_none_for_garbage() -> None:
    a = cursor()
    assert a.parse_stream("not json") is None
    assert a.parse_stream("") is None
