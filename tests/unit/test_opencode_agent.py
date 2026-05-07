"""Verify the opencode agent factory."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path

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
