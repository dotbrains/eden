"""Verify the generic cli_agent factory."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path

import pytest

from eden.agents import Agent, IterationContext
from eden.agents.cli import cli_agent
from eden.providers._types import ExecResult
from eden.streaming import StreamEvent

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


def test_factory_returns_agent_protocol() -> None:
    a = cli_agent(name="custom", model="m1", binary="my-cli")
    assert isinstance(a, Agent)
    assert a.name == "custom"
    assert a.model == "m1"


def test_default_build_command_appends_prompt_to_binary() -> None:
    a = cli_agent(name="custom", model="m", binary="my-cli")
    argv = a.build_command(_ctx(prompt="please run"))
    assert argv == ["my-cli", "please run"]


def test_extra_args_threaded_before_prompt() -> None:
    a = cli_agent(
        name="custom",
        model="m",
        binary="my-cli",
        extra_args=("--flag", "value"),
    )
    argv = a.build_command(_ctx(prompt="hi"))
    assert argv == ["my-cli", "--flag", "value", "hi"]


def test_custom_build_argv_overrides_default() -> None:
    def my_argv(ctx: IterationContext) -> list[str]:
        return ["echo", f"iter={ctx.iteration}", ctx.prompt]

    a = cli_agent(name="custom", model="m", binary="ignored", build_argv=my_argv)
    argv = a.build_command(_ctx(prompt="x"))
    assert argv == ["echo", "iter=0", "x"]


def test_default_parse_stream_returns_none() -> None:
    a = cli_agent(name="custom", model="m", binary="my-cli")
    assert a.parse_stream("any line") is None


def test_custom_parse_stream_overrides_default() -> None:
    def my_parser(line: str) -> StreamEvent | None:
        if line.startswith("OK"):
            return StreamEvent(
                type="text",
                agent_name="custom",
                iteration=0,
                timestamp=datetime.now(UTC),
                text=line,
            )
        return None

    a = cli_agent(name="custom", model="m", binary="my-cli", parse_stream=my_parser)
    assert a.parse_stream("noise") is None
    ev = a.parse_stream("OK done")
    assert ev is not None
    assert ev.type == "text"
    assert ev.text == "OK done"


def test_captures_sessions_default_false() -> None:
    a = cli_agent(name="custom", model="m", binary="my-cli")
    assert a.captures_sessions is False  # type: ignore[attr-defined]


def test_captures_sessions_true_honored() -> None:
    a = cli_agent(name="custom", model="m", binary="my-cli", captures_sessions=True)
    assert a.captures_sessions is True  # type: ignore[attr-defined]


def test_env_default_empty_satisfies_protocol() -> None:
    a = cli_agent(name="custom", model="m", binary="my-cli")
    assert isinstance(a, Agent)


def test_prompt_passed_unescaped() -> None:
    a = cli_agent(name="custom", model="m", binary="my-cli")
    argv = a.build_command(_ctx(prompt="echo $PWD; rm -rf /"))
    assert argv[-1] == "echo $PWD; rm -rf /"
