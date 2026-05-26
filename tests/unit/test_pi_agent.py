"""Verify the pi agent factory."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from pathlib import Path

import pytest

from eden.agents import IterationContext
from eden.agents.pi import pi
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


def test_pi_default_metadata() -> None:
    a = pi()
    assert a.name == "pi"
    assert a.model == "pi-3.5"


def test_pi_custom_model() -> None:
    a = pi(model="pi-4")
    assert a.model == "pi-4"


def test_pi_build_command_uses_pi_binary() -> None:
    a = pi()
    argv = a.build_command(_ctx(prompt="hello"))
    assert argv[0] == "pi"
    assert argv[-1] == "hello"


def test_pi_extra_args_threaded() -> None:
    a = pi(extra_args=("--verbose",))
    argv = a.build_command(_ctx(prompt="p"))
    assert "--verbose" in argv
    assert argv.index("--verbose") < argv.index("p")


def test_pi_parse_stream_wired_in() -> None:
    a = pi()
    line = json.dumps(
        {
            "type": "message_update",
            "assistantMessageEvent": {"type": "text_delta", "delta": "hello"},
        }
    )
    ev = a.parse_stream(line)
    assert ev is not None
    assert ev.type == "text"
    assert ev.text == "hello"
    assert ev.agent_name == "pi"


def test_pi_parse_stream_returns_none_for_unknown() -> None:
    a = pi()
    assert a.parse_stream("not json") is None
    assert a.parse_stream(json.dumps({"type": "noop"})) is None
