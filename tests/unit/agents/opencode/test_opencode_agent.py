"""Verify the opencode agent factory."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, cast

import pytest

from eden.agents import IterationContext
from eden.agents.opencode import opencode
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


def test_opencode_default_metadata() -> None:
    a = opencode()
    assert a.name == "opencode"
    assert a.model == "claude-opus-4"


def test_opencode_custom_model() -> None:
    a = opencode(model="claude-sonnet-4")
    assert a.model == "claude-sonnet-4"


def test_opencode_build_command_uses_opencode_binary() -> None:
    a = opencode()
    argv = a.build_command(_ctx(prompt="hello"))
    assert argv[0] == "opencode"
    assert argv[-1] == "hello"


def test_opencode_extra_args_threaded() -> None:
    a = opencode(extra_args=("--config", "x.yaml"))
    argv = a.build_command(_ctx(prompt="p"))
    assert "--config" in argv
    assert "x.yaml" in argv
    assert argv.index("x.yaml") < argv.index("p")


def test_opencode_argv_includes_run_subcommand_and_model() -> None:
    a = opencode(model="claude-sonnet-4")
    argv = a.build_command(_ctx(prompt="p"))
    assert argv[:2] == ["opencode", "run"]
    assert "--model" in argv
    assert argv[argv.index("--model") + 1] == "claude-sonnet-4"


def test_opencode_variant_threaded() -> None:
    a = opencode(model="m", variant="high")
    argv = a.build_command(_ctx(prompt="p"))
    assert "--variant" in argv
    assert argv[argv.index("--variant") + 1] == "high"
    assert argv.index("--variant") < argv.index("p")


def test_opencode_no_variant_omits_flag() -> None:
    a = opencode(model="m")
    argv = a.build_command(_ctx(prompt="p"))
    assert "--variant" not in argv


def test_opencode_format_json_always_present() -> None:
    a = opencode()
    argv = a.build_command(_ctx())
    assert "--format" in argv
    assert argv[argv.index("--format") + 1] == "json"


def test_opencode_dangerously_skip_permissions_default_off() -> None:
    a = opencode()
    argv = a.build_command(_ctx())
    assert "--dangerously-skip-permissions" not in argv


def test_opencode_dangerously_skip_permissions_appends_flag() -> None:
    a = opencode(dangerously_skip_permissions=True)
    argv = a.build_command(_ctx(prompt="p"))
    assert "--dangerously-skip-permissions" in argv
    assert argv.index("--dangerously-skip-permissions") < argv.index("p")


def test_opencode_agent_mode_threaded() -> None:
    a = opencode(agent="build")
    argv = a.build_command(_ctx(prompt="p"))
    assert "--agent" in argv
    assert argv[argv.index("--agent") + 1] == "build"
    assert argv.index("--agent") < argv.index("p")


def test_opencode_interactive_command_uses_tui_prompt_flag() -> None:
    a = opencode(model="m", agent="build", extra_args=("--config", "x.yaml"))
    build_interactive = cast(Any, a).build_interactive_command
    argv = build_interactive(_ctx(prompt="seed"))
    assert argv[:3] == ["opencode", "--model", "m"]
    assert "run" not in argv
    assert "--format" not in argv
    assert argv[argv.index("--agent") + 1] == "build"
    assert argv[argv.index("--prompt") + 1] == "seed"
    assert argv.index("x.yaml") < argv.index("--prompt")


def test_opencode_no_agent_mode_omits_flag() -> None:
    a = opencode()
    argv = a.build_command(_ctx())
    assert "--agent" not in argv


def test_opencode_parse_stream_wired_in() -> None:
    a = opencode()
    ev = a.parse_stream(json.dumps({"type": "step_start", "sessionID": "sid"}))
    assert ev is not None
    assert ev.type == "session_id"
    assert ev.session_id == "sid"
    assert ev.agent_name == "opencode"


def test_opencode_parse_stream_returns_none_for_unknown() -> None:
    a = opencode()
    assert a.parse_stream("garbage") is None
    assert a.parse_stream(json.dumps({"type": "heartbeat"})) is None
