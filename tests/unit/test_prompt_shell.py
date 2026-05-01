"""Verify !`cmd` shell-block expansion + public render_prompt."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path

import pytest

from eden.errors import PromptError
from eden.prompt import render_prompt
from eden.prompt._shell import expand_shell_blocks
from eden.providers._types import ExecResult


class _FakeHandle:
    worktree_path = Path("/workspace")

    def __init__(self, results: dict[str, ExecResult]) -> None:
        self._results = results
        self.calls: list[str] = []

    def exec(
        self,
        cmd: str,
        *,
        on_line: Callable[[str], None] | None = None,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> ExecResult:
        self.calls.append(cmd)
        return self._results[cmd]

    def copy_file_in(self, host: Path, sandbox: Path) -> None: ...
    def copy_file_out(self, sandbox: Path, host: Path) -> None: ...
    def close(self) -> None: ...


pytestmark = pytest.mark.unit


def test_no_blocks_returns_input() -> None:
    h = _FakeHandle({})
    out = expand_shell_blocks("plain text", handle=h)
    assert out == "plain text"
    assert h.calls == []


def test_single_block_substituted() -> None:
    h = _FakeHandle({"git status -s": ExecResult(stdout="?? a.py\n", stderr="", exit_code=0)})
    out = expand_shell_blocks("status: !`git status -s`", handle=h)
    assert out == "status: ?? a.py"


def test_multiple_blocks_run_sequentially() -> None:
    h = _FakeHandle(
        {
            "echo a": ExecResult(stdout="A\n", stderr="", exit_code=0),
            "echo b": ExecResult(stdout="B\n", stderr="", exit_code=0),
        }
    )
    out = expand_shell_blocks("!`echo a`-!`echo b`", handle=h)
    assert out == "A-B"
    assert h.calls == ["echo a", "echo b"]


def test_failure_raises_prompt_error() -> None:
    h = _FakeHandle({"bad": ExecResult(stdout="", stderr="boom", exit_code=1)})
    with pytest.raises(PromptError) as excinfo:
        expand_shell_blocks("!`bad`", handle=h)
    assert excinfo.value.code == "prompt.shell_block_failed"
    assert "bad" in excinfo.value.message


def test_block_strips_trailing_newline_only() -> None:
    h = _FakeHandle({"x": ExecResult(stdout="line1\nline2\n", stderr="", exit_code=0)})
    out = expand_shell_blocks("!`x`", handle=h)
    assert out == "line1\nline2"


def test_render_prompt_full_pipeline(tmp_path: Path) -> None:
    """Public render_prompt: substitution + shell expansion in order."""
    h = _FakeHandle({"date": ExecResult(stdout="2026-05-01\n", stderr="", exit_code=0)})
    out = render_prompt(
        text="branch={{SOURCE_BRANCH}} date=!`date`",
        args={},
        source_branch="feat/x",
        target_branch="main",
        handle=h,
    )
    assert out == "branch=feat/x date=2026-05-01"
