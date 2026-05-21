"""Verify !`cmd` shell-block expansion + public render_prompt."""

from __future__ import annotations

import threading
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
        stdin: str | None = None,
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


def test_multiple_blocks_spliced_in_source_order() -> None:
    h = _FakeHandle(
        {
            "echo a": ExecResult(stdout="A\n", stderr="", exit_code=0),
            "echo b": ExecResult(stdout="B\n", stderr="", exit_code=0),
        }
    )
    out = expand_shell_blocks("!`echo a`-!`echo b`", handle=h)
    assert out == "A-B"
    assert set(h.calls) == {"echo a", "echo b"}


def test_multiple_blocks_run_concurrently() -> None:
    # Deterministic concurrency check: a barrier requires both blocks to be
    # in-flight at the same time to release. If they ran serially the barrier
    # would deadlock and the test would hit the 5s timeout.
    barrier = threading.Barrier(parties=2, timeout=5.0)

    class _BarrierHandle(_FakeHandle):
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
            self.calls.append(cmd)
            barrier.wait()
            return self._results[cmd]

    h = _BarrierHandle(
        {
            "a": ExecResult(stdout="A\n", stderr="", exit_code=0),
            "b": ExecResult(stdout="B\n", stderr="", exit_code=0),
        }
    )
    out = expand_shell_blocks("!`a`-!`b`", handle=h)
    assert out == "A-B"


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


def test_render_prompt_built_ins_inside_shell_block() -> None:
    """``{{SOURCE_BRANCH}}`` substitutes inside a shell-block body."""
    h = _FakeHandle({"git log feat/x": ExecResult(stdout="abc123\n", stderr="", exit_code=0)})
    out = render_prompt(
        text="!`git log {{SOURCE_BRANCH}}`",
        args={},
        source_branch="feat/x",
        target_branch="main",
        handle=h,
    )
    assert out == "abc123"
    assert h.calls == ["git log feat/x"]


def test_render_prompt_shell_block_in_arg_value_is_inert() -> None:
    """Arg values containing ``!`...``` text must NOT trigger shell exec."""
    h = _FakeHandle({})
    out = render_prompt(
        text="user={{USER_INPUT}}",
        args={"USER_INPUT": "!`rm -rf /`"},
        source_branch="b",
        target_branch="main",
        handle=h,
    )
    # Arg substituted verbatim; no shell-block expansion ran on its value.
    assert out == "user=!`rm -rf /`"
    assert h.calls == []


def test_render_prompt_shell_block_then_arg_substitution() -> None:
    """Shell expansion runs on the raw template; args substitute afterwards."""
    h = _FakeHandle({"date": ExecResult(stdout="2026-05-01\n", stderr="", exit_code=0)})
    out = render_prompt(
        text="who={{NAME}} when=!`date`",
        args={"NAME": "ada"},
        source_branch="b",
        target_branch="main",
        handle=h,
    )
    assert out == "who=ada when=2026-05-01"
