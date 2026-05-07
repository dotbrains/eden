"""Run host hooks (sequential) and sandbox hooks (parallel) for a phase."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from eden._types import Timeouts
from eden.errors import HookFailed, HookTimeout
from eden.lifecycle._types import Hook, HookPhase, HostHooks, SandboxHooks
from eden.providers._protocols import SandboxHandle
from eden.tracing import span


def _phase_attr(phase: HookPhase) -> str:
    return phase.value


def run_host_hooks(
    *,
    phase: HookPhase,
    hooks: HostHooks,
    worktree_path: Path,
    env: Mapping[str, str],
    timeouts: Timeouts,
) -> None:
    attr = _phase_attr(phase)
    hook_list: tuple[Hook, ...] = getattr(hooks, attr, ())
    for hook in hook_list:
        deadline = hook.timeout if hook.timeout is not None else timeouts.hook_step
        merged: dict[str, str] = dict(os.environ)
        merged.update(env)
        if hook.env:
            merged.update(hook.env)
        with span(
            "eden.hook",
            attributes={
                "hook.location": "host",
                "hook.phase": phase.value,
                "hook.command": hook.cmd,
                "hook.timeout_s": deadline,
            },
        ):
            try:
                proc = subprocess.run(
                    hook.cmd,
                    shell=True,
                    cwd=str(hook.cwd) if hook.cwd is not None else str(worktree_path),
                    env=merged,
                    capture_output=True,
                    text=True,
                    timeout=deadline,
                )
            except subprocess.TimeoutExpired as exc:
                raise HookTimeout(
                    message=f"host hook {hook.cmd!r} timed out after {deadline}s",
                    hint="raise Hook.timeout or Timeouts.hook_step",
                    cause=exc,
                ) from exc
            if proc.returncode != 0:
                raise HookFailed(
                    message=(
                        f"host hook {hook.cmd!r} failed (exit {proc.returncode})\n{proc.stderr}"
                    ),
                )


def run_sandbox_hooks(
    *,
    phase: HookPhase,
    hooks: SandboxHooks,
    handle: SandboxHandle,
    env: Mapping[str, str],
    timeouts: Timeouts,
) -> None:
    attr = _phase_attr(phase)
    hook_list: tuple[Hook, ...] = getattr(hooks, attr, ())
    if not hook_list:
        return

    def _run_one(hook: Hook) -> tuple[Hook, str | None]:
        merged: dict[str, str] = dict(env)
        if hook.env:
            merged.update(hook.env)
        deadline = hook.timeout if hook.timeout is not None else timeouts.hook_step
        with span(
            "eden.hook",
            attributes={
                "hook.location": "sandbox",
                "hook.phase": phase.value,
                "hook.command": hook.cmd,
                "hook.timeout_s": deadline,
            },
        ):
            try:
                result = handle.exec(
                    hook.cmd,
                    cwd=hook.cwd,
                    env=merged,
                    timeout=deadline,
                )
            except Exception as exc:  # ExecTimeout etc.
                return hook, f"{type(exc).__name__}: {exc}"
            if result.exit_code != 0:
                return hook, f"exit {result.exit_code}: {result.stderr.strip()}"
            return hook, None

    with ThreadPoolExecutor(max_workers=max(1, len(hook_list))) as pool:
        results = list(pool.map(_run_one, hook_list))

    failures = [(h, msg) for (h, msg) in results if msg is not None]
    if failures:
        lines = "\n".join(f"  - {h.cmd}: {msg}" for h, msg in failures)
        raise HookFailed(
            message=f"{len(failures)} sandbox hook(s) failed for phase {phase.value}:\n{lines}",
        )
