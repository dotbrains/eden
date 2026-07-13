"""Tests for low-level ``stream_exec`` stdin forwarding."""

from __future__ import annotations

import sys

import pytest

from eden.sandboxes._exec import stream_exec

pytestmark = pytest.mark.unit


def test_stream_exec_forwards_stdin() -> None:
    result = stream_exec(
        [sys.executable, "-c", "import sys; sys.stdout.write(sys.stdin.read())"],
        cmd_for_error="cat-stdin",
        shell=False,
        stdin="payload-from-stdin\n",
    )
    assert result.exit_code == 0
    assert "payload-from-stdin" in result.stdout


def test_stream_exec_handles_large_stdin_payload() -> None:
    big = "X" * (256 * 1024) + "\n"
    result = stream_exec(
        [sys.executable, "-c", "import sys; print(len(sys.stdin.read()))"],
        cmd_for_error="len-stdin",
        shell=False,
        stdin=big,
    )
    assert result.exit_code == 0
    assert result.stdout.strip() == str(len(big))


def test_stream_exec_default_stdin_is_none() -> None:
    result = stream_exec(
        [sys.executable, "-c", "print('ok')"],
        cmd_for_error="no-stdin",
        shell=False,
    )
    assert result.exit_code == 0
