"""Async API surface — thin ``asyncio.to_thread`` wrappers around the sync API.

The sync API in :mod:`eden` is the source of truth (see ADR 0002). These
wrappers exist so async callers (FastAPI handlers, awaited notebook cells,
``asyncio.gather`` fan-out code) can write::

    result = await eden.aio.run(agent=..., sandbox=..., prompt="...")

instead of wrapping every call in ``asyncio.to_thread`` themselves. Each
wrapper preserves its sync counterpart's signature and return type — the
implementation is a single ``return await asyncio.to_thread(...)`` per
function — so type checkers and IDE autocomplete behave identically.

The blocking work runs on asyncio's default ``ThreadPoolExecutor``. Users
running many concurrent eden tasks (>32 by default) should size the
executor with ``asyncio.get_running_loop().set_default_executor(...)``.
See ADR 0011 for the full rationale.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from pathlib import Path

from eden import (
    Agent,
    BranchStrategy,
    Hooks,
    InteractiveResult,
    Mount,
    Sandbox,
    Timeouts,
)
from eden import create_sandbox as _sync_create_sandbox
from eden import interactive as _sync_interactive
from eden.aio._run import run
from eden.providers._protocols import SandboxProvider
from eden.worktree._create import WorktreeHandle


async def create_sandbox(
    *,
    sandbox: SandboxProvider,
    branch: str | None = None,
    branch_strategy: BranchStrategy | None = None,
    base_branch: str | None = None,
    worktree: WorktreeHandle | None = None,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    mounts: tuple[Mount, ...] | None = None,
    name: str | None = None,
    hooks: Hooks | None = None,
    copy_to_worktree: list[str] | None = None,
    throw_on_duplicate_worktree: bool = True,
    timeouts: Timeouts | None = None,
) -> Sandbox:
    """Async wrapper around :func:`eden.create_sandbox`.

    The returned :class:`eden.Sandbox` exposes a sync ``.run(...)`` method;
    callers that want to ``await`` it write
    ``await asyncio.to_thread(s.run, agent=...)``. ADR 0011 explains why
    eden does not add async methods directly to the dataclass.
    """
    return await asyncio.to_thread(
        _sync_create_sandbox,
        sandbox=sandbox,
        branch=branch,
        branch_strategy=branch_strategy,
        base_branch=base_branch,
        worktree=worktree,
        cwd=cwd,
        env=env,
        mounts=mounts,
        name=name,
        hooks=hooks,
        copy_to_worktree=copy_to_worktree,
        throw_on_duplicate_worktree=throw_on_duplicate_worktree,
        timeouts=timeouts,
    )


async def interactive(
    *,
    agent: Agent,
    sandbox: SandboxProvider | None = None,
    prompt: str | None = None,
    prompt_file: str | Path | None = None,
    prompt_args: Mapping[str, object] | None = None,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    branch_strategy: BranchStrategy | None = None,
    base_branch: str | None = None,
    name: str | None = None,
    hooks: Hooks | None = None,
    copy_to_worktree: list[str] | None = None,
    throw_on_duplicate_worktree: bool = True,
) -> InteractiveResult:
    """Async wrapper around :func:`eden.interactive`.

    Interactive sessions block on the user's TTY input, so the wrapper is
    only useful inside async code that already needs to ``await`` other
    work alongside the agent — typically driver scripts that interleave
    interactive sessions with non-interactive runs.
    """
    return await asyncio.to_thread(
        _sync_interactive,
        agent=agent,
        sandbox=sandbox,
        prompt=prompt,
        prompt_file=prompt_file,
        prompt_args=prompt_args,
        cwd=cwd,
        env=env,
        branch_strategy=branch_strategy,
        base_branch=base_branch,
        name=name,
        hooks=hooks,
        copy_to_worktree=copy_to_worktree,
        throw_on_duplicate_worktree=throw_on_duplicate_worktree,
    )


__all__ = ["create_sandbox", "interactive", "run"]
