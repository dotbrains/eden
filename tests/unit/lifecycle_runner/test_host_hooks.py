"""Verify host hook runner behavior."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from eden._types import Timeouts
from eden.errors import HookFailed, HookTimeout
from eden.lifecycle import Hook, HookPhase, HostHooks
from eden.lifecycle._runner import run_host_hooks

pytestmark = pytest.mark.unit


def test_host_hooks_run_sequentially_in_order(tmp_path: Path) -> None:
    hooks = HostHooks(
        on_worktree_ready=(
            Hook(cmd=f'"{sys.executable}" -c "print(1)"'),
            Hook(cmd=f'"{sys.executable}" -c "print(2)"'),
        )
    )
    run_host_hooks(
        phase=HookPhase.OnWorktreeReady,
        hooks=hooks,
        worktree_path=tmp_path,
        env={},
        timeouts=Timeouts(),
    )


def test_host_hook_failure_raises_hook_failed(tmp_path: Path) -> None:
    hooks = HostHooks(
        on_worktree_ready=(Hook(cmd=f'"{sys.executable}" -c "import sys; sys.exit(7)"'),)
    )
    with pytest.raises(HookFailed) as excinfo:
        run_host_hooks(
            phase=HookPhase.OnWorktreeReady,
            hooks=hooks,
            worktree_path=tmp_path,
            env={},
            timeouts=Timeouts(),
        )
    assert "exit 7" in excinfo.value.message or "7" in excinfo.value.message


def test_host_hook_timeout_raises_hook_timeout(tmp_path: Path) -> None:
    hooks = HostHooks(
        on_worktree_ready=(
            Hook(
                cmd=f'"{sys.executable}" -c "import time; time.sleep(60)"',
                timeout=0.5,
            ),
        )
    )
    with pytest.raises(HookTimeout):
        run_host_hooks(
            phase=HookPhase.OnWorktreeReady,
            hooks=hooks,
            worktree_path=tmp_path,
            env={},
            timeouts=Timeouts(hook_step=0.5),
        )


def test_host_hook_sudo_rejected(tmp_path: Path) -> None:
    hooks = HostHooks(on_worktree_ready=(Hook(cmd="echo hi", sudo=True),))
    with pytest.raises(HookFailed, match="sudo"):
        run_host_hooks(
            phase=HookPhase.OnWorktreeReady,
            hooks=hooks,
            worktree_path=tmp_path,
            env={},
            timeouts=Timeouts(),
        )


def test_empty_host_hooks_noop(tmp_path: Path) -> None:
    run_host_hooks(
        phase=HookPhase.OnWorktreeReady,
        hooks=HostHooks(),
        worktree_path=tmp_path,
        env={},
        timeouts=Timeouts(),
    )
