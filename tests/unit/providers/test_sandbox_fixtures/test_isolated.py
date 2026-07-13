"""Tests for the in-tree ``test_isolated`` provider."""

from __future__ import annotations

from pathlib import Path

import pytest

from eden.providers._protocols import IsolatedSandboxHandle, SandboxProvider
from eden.providers._types import CreateOptions, ExecResult
from eden.sandboxes.test_bind_mount import CallLog, ExecCall
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
