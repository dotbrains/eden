"""Tests that local sandbox handles forward ``stdin=`` through exec."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from eden.providers._types import ExecResult
from eden.sandboxes.no_sandbox import provider as no_sandbox
from eden.sandboxes.test_bind_mount import CallLog, ExecCall
from eden.sandboxes.test_bind_mount import provider as bind_mount_provider
from eden.sandboxes.test_isolated import provider as isolated_provider
from tests.unit.exec_stdin.conftest import cat_stdin_script, opts

pytestmark = pytest.mark.unit


def test_no_sandbox_forwards_stdin(tmp_path: Path) -> None:
    provider = no_sandbox()
    handle = provider.create(opts(tmp_path))
    script = cat_stdin_script(tmp_path)
    try:
        result = handle.exec(f"{sys.executable} {script}", stdin="forwarded\n")
        assert result.exit_code == 0
        assert "forwarded" in result.stdout
    finally:
        handle.close()


def test_test_bind_mount_records_stdin_in_call_log(tmp_path: Path) -> None:
    log = CallLog()
    provider = bind_mount_provider(call_log=log)
    handle = provider.create(opts(tmp_path))
    try:

        def stub(call: ExecCall) -> ExecResult:
            assert call.stdin == "expected-stdin"
            return ExecResult(stdout="ok", stderr="", exit_code=0)

        provider_with_handler = bind_mount_provider(exec_handler=stub, call_log=log)
        handle_with_handler = provider_with_handler.create(opts(tmp_path))
        try:
            handle_with_handler.exec("noop", stdin="expected-stdin")
        finally:
            handle_with_handler.close()
    finally:
        handle.close()

    matching = [call for call in log.exec_calls if call.stdin == "expected-stdin"]
    assert len(matching) == 1


def test_test_bind_mount_forwards_stdin_to_real_subprocess(tmp_path: Path) -> None:
    provider = bind_mount_provider()
    handle = provider.create(opts(tmp_path))
    script = cat_stdin_script(tmp_path)
    try:
        result = handle.exec(f"{sys.executable} {script}", stdin="hello-via-handle\n")
        assert result.exit_code == 0
        assert "hello-via-handle" in result.stdout
    finally:
        handle.close()


def test_test_isolated_forwards_stdin_to_real_subprocess(tmp_git_repo: Path) -> None:
    provider = isolated_provider()
    handle = provider.create(opts(tmp_git_repo))
    script = cat_stdin_script(tmp_git_repo)
    try:
        result = handle.exec(f"{sys.executable} {script}", stdin="iso-stdin\n")
        assert result.exit_code == 0
        assert "iso-stdin" in result.stdout
    finally:
        handle.close()
