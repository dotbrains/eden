"""Tests for the in-tree ``test_bind_mount`` provider."""

from __future__ import annotations

from pathlib import Path

import pytest

from eden.providers._protocols import BindMountSandboxHandle, SandboxProvider
from eden.providers._types import CreateOptions, ExecResult
from eden.sandboxes.test_bind_mount import CallLog, CopyCall, ExecCall
from eden.sandboxes.test_bind_mount import provider as bind_mount_provider

pytestmark = pytest.mark.unit


def _opts(worktree: Path, host: Path) -> CreateOptions:
    return CreateOptions(
        branch="main",
        worktree_path=worktree,
        host_repo_path=host,
        env={},
        mounts=(),
        name_hint=None,
    )


def test_bind_mount_provider_is_sandbox_provider() -> None:
    p = bind_mount_provider()
    assert isinstance(p, SandboxProvider)
    assert p.name == "test-bind-mount"
    assert p.kind == "bind_mount"


def test_bind_mount_create_returns_bind_mount_handle(tmp_path: Path) -> None:
    p = bind_mount_provider()
    h = p.create(_opts(tmp_path, tmp_path))
    try:
        assert isinstance(h, BindMountSandboxHandle)
        assert h.worktree_path.is_dir()
        # Sandbox path is *not* the host worktree — it's the provider's
        # carved tempdir.
        assert h.worktree_path != tmp_path
    finally:
        h.close()


def test_bind_mount_records_exec_calls(tmp_path: Path) -> None:
    log = CallLog()
    p = bind_mount_provider(call_log=log)
    h = p.create(_opts(tmp_path, tmp_path))
    try:
        h.exec("echo hello", timeout=5.0)
    finally:
        h.close()

    assert len(log.exec_calls) == 1
    assert log.exec_calls[0].cmd == "echo hello"
    assert log.exec_calls[0].timeout == 5.0
    assert log.closed is True


def test_bind_mount_exec_handler_short_circuits(tmp_path: Path) -> None:
    captured: list[ExecCall] = []

    def stub(call: ExecCall) -> ExecResult:
        captured.append(call)
        return ExecResult(stdout="stubbed\n", stderr="", exit_code=0)

    p = bind_mount_provider(exec_handler=stub)
    h = p.create(_opts(tmp_path, tmp_path))
    try:
        result = h.exec("ignored cmd")
        assert result.stdout == "stubbed\n"
        assert result.exit_code == 0
    finally:
        h.close()
    assert len(captured) == 1
    assert captured[0].cmd == "ignored cmd"


def test_bind_mount_exec_handler_forwards_on_line(tmp_path: Path) -> None:
    def stub(_: ExecCall) -> ExecResult:
        return ExecResult(stdout="a\nb\nc\n", stderr="", exit_code=0)

    lines: list[str] = []
    p = bind_mount_provider(exec_handler=stub)
    h = p.create(_opts(tmp_path, tmp_path))
    try:
        h.exec("x", on_line=lines.append)
    finally:
        h.close()
    assert lines == ["a", "b", "c"]


def test_bind_mount_copy_records_calls(tmp_path: Path) -> None:
    log = CallLog()
    p = bind_mount_provider(call_log=log)
    h = p.create(_opts(tmp_path, tmp_path))
    src = tmp_path / "src.txt"
    src.write_text("payload")
    dst_inside = h.worktree_path / "dst.txt"
    try:
        h.copy_file_in(src, dst_inside)
        assert dst_inside.read_text() == "payload"
        out_path = tmp_path / "out.txt"
        h.copy_file_out(dst_inside, out_path)
        assert out_path.read_text() == "payload"
    finally:
        h.close()
    assert [c.direction for c in log.copy_calls] == ["in", "out"]
    assert isinstance(log.copy_calls[0], CopyCall)


def test_bind_mount_close_removes_sandbox_root(tmp_path: Path) -> None:
    p = bind_mount_provider()
    h = p.create(_opts(tmp_path, tmp_path))
    wt = h.worktree_path
    sandbox_root = wt.parent
    h.close()
    assert not sandbox_root.exists()
