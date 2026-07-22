"""Verify no_sandbox exec behavior."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Protocol, cast

import pytest

from eden.sandboxes.no_sandbox import provider
from tests.unit.no_sandbox.conftest import opts

pytestmark = pytest.mark.unit


class _InteractiveHandle(Protocol):
    def interactive_exec(self, argv: list[str]) -> int: ...

    def close(self) -> None: ...


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


def test_interactive_exec_uses_shell_on_windows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, Any] = {}

    class _FakePopen:
        def __init__(self, argv: list[str], **kwargs: Any) -> None:
            captured["argv"] = argv
            captured.update(kwargs)

        def wait(self, timeout: float | None = None) -> int:
            return 0

        def terminate(self) -> None:
            return None

        def kill(self) -> None:
            return None

    monkeypatch.setattr("eden.sandboxes.no_sandbox.sys.platform", "win32")
    monkeypatch.setattr("eden.sandboxes.no_sandbox.subprocess.Popen", _FakePopen)

    handle = cast(_InteractiveHandle, provider().create(opts(tmp_path)))
    try:
        result = handle.interactive_exec(["claude", "--model", "x"])
    finally:
        handle.close()

    assert result == 0
    assert captured["argv"] == ["claude", "--model", "x"]
    assert captured["shell"] is True


def test_interactive_exec_keeps_direct_argv_on_posix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, Any] = {}

    class _FakePopen:
        def __init__(self, argv: list[str], **kwargs: Any) -> None:
            captured["argv"] = argv
            captured.update(kwargs)

        def wait(self, timeout: float | None = None) -> int:
            return 0

        def terminate(self) -> None:
            return None

        def kill(self) -> None:
            return None

    monkeypatch.setattr("eden.sandboxes.no_sandbox.sys.platform", "linux")
    monkeypatch.setattr("eden.sandboxes.no_sandbox.subprocess.Popen", _FakePopen)

    handle = cast(_InteractiveHandle, provider().create(opts(tmp_path)))
    try:
        result = handle.interactive_exec(["claude", "--model", "x"])
    finally:
        handle.close()

    assert result == 0
    assert captured["argv"] == ["claude", "--model", "x"]
    assert captured["shell"] is False
