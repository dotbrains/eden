"""Verify sandbox hook runner behavior."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from eden._types import Timeouts
from eden.errors import HookFailed
from eden.lifecycle import Hook, HookPhase, SandboxHooks
from eden.lifecycle._runner import run_sandbox_hooks
from tests.unit.lifecycle_runner.conftest import FakeHandle

pytestmark = pytest.mark.unit


def test_sandbox_hooks_run_parallel(tmp_path: Path) -> None:
    # 0.4s sleep x 4 hooks: sequential = 1.6s, parallel ~ 0.4s + threadpool
    # overhead. Threshold 1.5s gives 0.1s of slack against the sequential floor.
    seen: list[str] = []
    handle = FakeHandle(worktree_path=tmp_path, seen=seen, sleep_per_call=0.4)
    hooks = SandboxHooks(
        on_sandbox_ready=(
            Hook(cmd="A"),
            Hook(cmd="B"),
            Hook(cmd="C"),
            Hook(cmd="D"),
        )
    )
    start = time.monotonic()
    run_sandbox_hooks(
        phase=HookPhase.OnSandboxReady,
        hooks=hooks,
        handle=handle,
        env={},
        timeouts=Timeouts(),
    )
    elapsed = time.monotonic() - start
    assert sorted(seen) == ["A", "B", "C", "D"]
    assert elapsed < 1.5


def test_sandbox_hook_failures_aggregated(tmp_path: Path) -> None:
    seen: list[str] = []
    handle = FakeHandle(
        worktree_path=tmp_path,
        seen=seen,
        fails_for=("X", "Y"),
    )
    hooks = SandboxHooks(
        on_sandbox_ready=(
            Hook(cmd="ok"),
            Hook(cmd="X"),
            Hook(cmd="Y"),
        )
    )
    with pytest.raises(HookFailed) as excinfo:
        run_sandbox_hooks(
            phase=HookPhase.OnSandboxReady,
            hooks=hooks,
            handle=handle,
            env={},
            timeouts=Timeouts(),
        )
    assert "X" in excinfo.value.message
    assert "Y" in excinfo.value.message


def test_sandbox_hook_sudo_wraps_command(tmp_path: Path) -> None:
    seen: list[str] = []
    handle = FakeHandle(worktree_path=tmp_path, seen=seen)
    hooks = SandboxHooks(
        on_sandbox_ready=(Hook(cmd="apt-get install -y ffmpeg", sudo=True),),
    )
    run_sandbox_hooks(
        phase=HookPhase.OnSandboxReady,
        hooks=hooks,
        handle=handle,
        env={},
        timeouts=Timeouts(),
    )
    assert len(seen) == 1
    assert seen[0].startswith("sudo -E -- sh -c ")
    assert "apt-get install -y ffmpeg" in seen[0]


def test_sandbox_hook_no_sudo_leaves_command_alone(tmp_path: Path) -> None:
    seen: list[str] = []
    handle = FakeHandle(worktree_path=tmp_path, seen=seen)
    hooks = SandboxHooks(on_sandbox_ready=(Hook(cmd="echo hi"),))
    run_sandbox_hooks(
        phase=HookPhase.OnSandboxReady,
        hooks=hooks,
        handle=handle,
        env={},
        timeouts=Timeouts(),
    )
    assert seen == ["echo hi"]


def test_empty_sandbox_hooks_noop(tmp_path: Path) -> None:
    handle = FakeHandle(worktree_path=tmp_path, seen=[])
    run_sandbox_hooks(
        phase=HookPhase.OnSandboxReady,
        hooks=SandboxHooks(),
        handle=handle,
        env={},
        timeouts=Timeouts(),
    )
