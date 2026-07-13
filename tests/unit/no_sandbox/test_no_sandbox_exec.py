"""Verify no_sandbox exec behavior."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from eden.sandboxes.no_sandbox import provider
from tests.unit.no_sandbox.conftest import opts

pytestmark = pytest.mark.unit


def test_handle_exec_runs_in_worktree(tmp_path: Path) -> None:
    handle = provider().create(opts(tmp_path))
    try:
        result = handle.exec(f'"{sys.executable}" -c "import os; print(os.getcwd())"')
        assert result.exit_code == 0
        assert str(tmp_path) in result.stdout
    finally:
        handle.close()


def test_handle_exec_explicit_cwd_overrides(tmp_path: Path) -> None:
    sub = tmp_path / "sub"
    sub.mkdir()
    handle = provider().create(opts(tmp_path))
    try:
        result = handle.exec(
            f'"{sys.executable}" -c "import os; print(os.getcwd())"',
            cwd=sub,
        )
        assert str(sub) in result.stdout
    finally:
        handle.close()


def test_provider_bounds_streamed_exec_result(tmp_path: Path) -> None:
    handle = provider(max_output_tail_chars=12).create(opts(tmp_path))
    try:
        seen: list[str] = []
        result = handle.exec(
            f"\"{sys.executable}\" -c \"print('alpha'); print('beta'); print('gamma')\"",
            on_line=seen.append,
        )
        assert seen == ["alpha", "beta", "gamma"]
        assert len(result.stdout) <= 12
        assert "gamma" in result.stdout
        assert "alpha" not in result.stdout
    finally:
        handle.close()


def test_provider_env_flows_to_exec(tmp_path: Path) -> None:
    handle = provider(env={"EDEN_NO_SANDBOX_TEST": "provider"}).create(opts(tmp_path))
    try:
        result = handle.exec(
            f'"{sys.executable}" -c "import os; print(os.environ[\'EDEN_NO_SANDBOX_TEST\'])"'
        )
        assert result.stdout.strip() == "provider"
    finally:
        handle.close()


def test_exec_env_overrides_provider_env(tmp_path: Path) -> None:
    handle = provider(env={"EDEN_NO_SANDBOX_TEST": "provider"}).create(opts(tmp_path))
    try:
        result = handle.exec(
            f'"{sys.executable}" -c "import os; print(os.environ[\'EDEN_NO_SANDBOX_TEST\'])"',
            env={"EDEN_NO_SANDBOX_TEST": "call"},
        )
        assert result.stdout.strip() == "call"
    finally:
        handle.close()
