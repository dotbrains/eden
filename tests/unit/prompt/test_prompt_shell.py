"""Verify !`cmd` shell-block expansion + public render_prompt."""

from __future__ import annotations

import threading
from collections.abc import Callable, Mapping
from pathlib import Path

import pytest

from eden.errors import PromptError
from eden.prompt._shell import expand_shell_blocks
from eden.providers._types import ExecResult

from ._shell_helpers import FakeHandle

pytestmark = pytest.mark.unit


def test_no_blocks_returns_input() -> None:
    h = FakeHandle({})
    out = expand_shell_blocks("plain text", handle=h)
    assert out == "plain text"
    assert h.calls == []


def test_single_block_substituted() -> None:
    h = FakeHandle({"git status -s": ExecResult(stdout="?? a.py\n", stderr="", exit_code=0)})
    out = expand_shell_blocks("status: !`git status -s`", handle=h)
    assert out == "status: ?? a.py"


def test_multiple_blocks_spliced_in_source_order() -> None:
    h = FakeHandle(
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

    class _BarrierHandle(FakeHandle):
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
    h = FakeHandle({"bad": ExecResult(stdout="", stderr="boom", exit_code=1)})
    with pytest.raises(PromptError) as excinfo:
        expand_shell_blocks("!`bad`", handle=h)
    assert excinfo.value.code == "prompt.shell_block_failed"
    assert "bad" in excinfo.value.message


def test_failure_surfaces_exit_code_as_attribute() -> None:
    """``PromptError.exit_code`` is set so callers can branch programmatically."""
    h = FakeHandle({"x": ExecResult(stdout="", stderr="", exit_code=127)})
    with pytest.raises(PromptError) as excinfo:
        expand_shell_blocks("!`x`", handle=h)
    assert excinfo.value.exit_code == 127


def test_non_exec_prompt_error_has_no_exit_code() -> None:
    """``exit_code`` stays ``None`` for non-subprocess failures."""
    e = PromptError(code="prompt.unknown_key", message="bad key")
    assert e.exit_code is None


def test_block_strips_trailing_newline_only() -> None:
    h = FakeHandle({"x": ExecResult(stdout="line1\nline2\n", stderr="", exit_code=0)})
    out = expand_shell_blocks("!`x`", handle=h)
    assert out == "line1\nline2"
