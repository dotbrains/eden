"""Verify the codex agent factory."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path

import pytest

from eden.agents import IterationContext
from eden.agents.codex import codex
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


def test_codex_default_metadata() -> None:
    a = codex()
    assert a.name == "codex"
    assert a.model == "gpt-5"


def test_codex_custom_model() -> None:
    a = codex(model="gpt-4o")
    assert a.model == "gpt-4o"


def test_codex_build_command_uses_codex_binary() -> None:
    a = codex()
    argv = a.build_command(_ctx(prompt="hello"))
    assert argv[0] == "codex"
    assert argv[-1] == "hello"


def test_codex_extra_args_threaded() -> None:
    a = codex(extra_args=("--no-cache",))
    argv = a.build_command(_ctx(prompt="x"))
    assert "--no-cache" in argv
    assert argv.index("--no-cache") < argv.index("x")
