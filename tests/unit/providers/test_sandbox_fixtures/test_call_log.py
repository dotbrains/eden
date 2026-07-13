"""Tests for shared test sandbox provider call logging."""

from __future__ import annotations

from pathlib import Path

import pytest

from eden.providers._types import CreateOptions
from eden.sandboxes.test_bind_mount import CallLog
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
