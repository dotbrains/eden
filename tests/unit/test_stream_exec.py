"""Verify stream_exec subprocess streaming helper."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from eden.sandboxes._exec import stream_exec
from eden.sandboxes.errors import ExecTimeout

pytestmark = pytest.mark.unit


def test_zero_exit_captures_stdout() -> None:
    result = stream_exec(
        [sys.executable, "-c", "print('hello')"],
        cmd_for_error="python -c print",
        shell=False,
    )
    assert result.exit_code == 0
    assert "hello" in result.stdout
    assert result.ok is True


def test_nonzero_exit_returned_in_result() -> None:
    result = stream_exec(
        [sys.executable, "-c", "import sys; sys.exit(7)"],
        cmd_for_error="python -c sys.exit(7)",
        shell=False,
    )
    assert result.exit_code == 7
    assert result.ok is False


def test_stderr_captured_separately() -> None:
    result = stream_exec(
        [
            sys.executable,
            "-c",
            "import sys; print('e', file=sys.stderr); print('o')",
        ],
        cmd_for_error="python -c stderr",
        shell=False,
    )
    assert "o" in result.stdout
    assert "e" in result.stderr


def test_on_line_callback_invoked_per_line() -> None:
    seen: list[str] = []
    stream_exec(
        [sys.executable, "-c", "print('a'); print('b')"],
        cmd_for_error="python -c print",
        shell=False,
        on_line=seen.append,
    )
    assert "a" in seen
    assert "b" in seen


def test_streamed_result_stdout_can_be_bounded() -> None:
    seen: list[str] = []
    result = stream_exec(
        [sys.executable, "-c", "print('alpha'); print('beta'); print('gamma')"],
        cmd_for_error="python -c print",
        shell=False,
        on_line=seen.append,
        max_output_tail_chars=12,
    )
    assert seen == ["alpha", "beta", "gamma"]
    assert len(result.stdout) <= 12
    assert "gamma" in result.stdout
    assert "alpha" not in result.stdout


def test_output_tail_bound_only_applies_to_streamed_exec() -> None:
    result = stream_exec(
        [sys.executable, "-c", "print('alpha'); print('beta'); print('gamma')"],
        cmd_for_error="python -c print",
        shell=False,
        max_output_tail_chars=12,
    )
    assert "alpha" in result.stdout
    assert "gamma" in result.stdout


def test_shell_mode_uses_shell() -> None:
    result = stream_exec(
        "echo shellmode",
        cmd_for_error="echo shellmode",
        shell=True,
    )
    assert result.exit_code == 0
    assert "shellmode" in result.stdout


def test_cwd_is_respected(tmp_path: Path) -> None:
    result = stream_exec(
        [sys.executable, "-c", "import os; print(os.getcwd())"],
        cmd_for_error="getcwd",
        shell=False,
        cwd=tmp_path,
    )
    assert str(tmp_path) in result.stdout


def test_env_passthrough() -> None:
    result = stream_exec(
        [
            sys.executable,
            "-c",
            "import os; print(os.environ.get('EDEN_TEST_KEY', '<missing>'))",
        ],
        cmd_for_error="env",
        shell=False,
        env={"EDEN_TEST_KEY": "passed"},
    )
    assert "passed" in result.stdout


def test_timeout_raises_exec_timeout() -> None:
    with pytest.raises(ExecTimeout) as excinfo:
        stream_exec(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            cmd_for_error="sleep 60",
            shell=False,
            timeout=0.5,
        )
    assert excinfo.value.timeout == 0.5
