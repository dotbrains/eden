"""Tests for the in-tree ``test_bind_mount`` and ``test_isolated`` providers."""

from __future__ import annotations

from pathlib import Path

import pytest

from eden.providers._protocols import (
    BindMountSandboxHandle,
    IsolatedSandboxHandle,
    SandboxProvider,
)
from eden.providers._types import CreateOptions, ExecResult
from eden.sandboxes.test_bind_mount import (
    CallLog,
    CopyCall,
    ExecCall,
)
from eden.sandboxes.test_bind_mount import (
    provider as bind_mount_provider,
)
from eden.sandboxes.test_isolated import provider as isolated_provider

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


def test_isolated_provider_is_isolated(tmp_path: Path) -> None:
    p = isolated_provider()
    assert isinstance(p, SandboxProvider)
    assert p.kind == "isolated"
    assert p.name == "test-isolated"


def test_isolated_create_clones_worktree(tmp_path: Path) -> None:
    # Populate the host worktree.
    host_wt = tmp_path / "host_wt"
    host_wt.mkdir()
    (host_wt / "a.txt").write_text("alpha\n")
    (host_wt / "b.txt").write_text("beta\n")

    p = isolated_provider()
    h = p.create(_opts(host_wt, tmp_path))
    try:
        assert isinstance(h, IsolatedSandboxHandle)
        assert (h.worktree_path / "a.txt").read_text() == "alpha\n"
        assert (h.worktree_path / "b.txt").read_text() == "beta\n"
    finally:
        h.close()


def test_isolated_finalize_replays_changes(tmp_path: Path) -> None:
    host_wt = tmp_path / "host_wt"
    host_wt.mkdir()
    (host_wt / "x.txt").write_text("v1\n")

    p = isolated_provider()
    h = p.create(_opts(host_wt, tmp_path))
    assert isinstance(h, IsolatedSandboxHandle)
    try:
        # Modify in the sandbox.
        (h.worktree_path / "x.txt").write_text("v2\n")
        (h.worktree_path / "new.txt").write_text("freshly added\n")

        result = h.finalize(host_wt)
        assert result.applied is True
        assert (host_wt / "x.txt").read_text() == "v2\n"
        assert (host_wt / "new.txt").read_text() == "freshly added\n"
    finally:
        h.close()


def test_isolated_finalize_records_call(tmp_path: Path) -> None:
    host_wt = tmp_path / "host_wt"
    host_wt.mkdir()
    p = isolated_provider()
    h = p.create(_opts(host_wt, tmp_path))
    assert isinstance(h, IsolatedSandboxHandle)
    try:
        h.finalize(host_wt)
        h.finalize(host_wt)
        # Internal attr — kept for diagnostics, not part of the Protocol.
        assert len(h.finalize_calls) == 2  # type: ignore[attr-defined]
    finally:
        h.close()


def test_isolated_close_removes_sandbox_root(tmp_path: Path) -> None:
    host_wt = tmp_path / "host_wt"
    host_wt.mkdir()
    p = isolated_provider()
    h = p.create(_opts(host_wt, tmp_path))
    wt = h.worktree_path
    sandbox_root = wt.parent
    h.close()
    assert not sandbox_root.exists()


def test_isolated_exec_handler_short_circuits(tmp_path: Path) -> None:
    host_wt = tmp_path / "host_wt"
    host_wt.mkdir()

    def stub(_: ExecCall) -> ExecResult:
        return ExecResult(stdout="ok", stderr="", exit_code=0)

    log = CallLog()
    p = isolated_provider(exec_handler=stub, call_log=log)
    h = p.create(_opts(host_wt, tmp_path))
    try:
        h.exec("anything")
    finally:
        h.close()
    assert len(log.exec_calls) == 1


def test_call_log_reset_clears_state(tmp_path: Path) -> None:
    log = CallLog()
    p = bind_mount_provider(call_log=log)
    h = p.create(_opts(tmp_path, tmp_path))
    try:
        h.exec("echo a", timeout=None)
    finally:
        h.close()
    assert log.exec_calls
    assert log.closed
    log.reset()
    assert not log.exec_calls
    assert not log.closed
