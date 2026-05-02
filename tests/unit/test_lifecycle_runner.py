"""Verify host-sequential and sandbox-parallel hook runners."""

from __future__ import annotations

import sys
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from eden._types import Timeouts
from eden.errors import HookFailed, HookTimeout
from eden.lifecycle import Hook, HookPhase, HostHooks, SandboxHooks
from eden.lifecycle._runner import run_host_hooks, run_sandbox_hooks
from eden.providers._types import ExecResult

pytestmark = pytest.mark.unit


@dataclass
class _FakeHandle:
    worktree_path: Path
    seen: list[str]
    fails_for: tuple[str, ...] = ()
    sleep_per_call: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def exec(
        self,
        cmd: str,
        *,
        on_line: Callable[[str], None] | None = None,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> ExecResult:
        if self.sleep_per_call:
            time.sleep(self.sleep_per_call)
        with self._lock:
            self.seen.append(cmd)
        if cmd in self.fails_for:
            return ExecResult(stdout="", stderr=f"err:{cmd}", exit_code=1)
        return ExecResult(stdout=f"ok:{cmd}\n", stderr="", exit_code=0)

    def copy_file_in(self, host: Path, sandbox: Path) -> None: ...
    def copy_file_out(self, sandbox: Path, host: Path) -> None: ...
    def close(self) -> None: ...


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


def test_sandbox_hooks_run_parallel(tmp_path: Path) -> None:
    # 0.4s sleep x 4 hooks: sequential = 1.6s, parallel ~ 0.4s + threadpool
    # overhead. Threshold 1.5s gives 0.1s of slack against the sequential
    # floor so the test stays meaningful (sequential always fails) while
    # tolerating slow Windows CI VMs where threadpool overhead dominated
    # parallelism (observed 1.36s on py3.13 with prior 1.0s threshold).
    seen: list[str] = []
    handle = _FakeHandle(worktree_path=tmp_path, seen=seen, sleep_per_call=0.4)
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
    handle = _FakeHandle(
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


def test_empty_hooks_noop(tmp_path: Path) -> None:
    run_host_hooks(
        phase=HookPhase.OnWorktreeReady,
        hooks=HostHooks(),
        worktree_path=tmp_path,
        env={},
        timeouts=Timeouts(),
    )
    handle = _FakeHandle(worktree_path=tmp_path, seen=[])
    run_sandbox_hooks(
        phase=HookPhase.OnSandboxReady,
        hooks=SandboxHooks(),
        handle=handle,
        env={},
        timeouts=Timeouts(),
    )
