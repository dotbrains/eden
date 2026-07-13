"""Sandbox finalization helpers for the run loop."""

from __future__ import annotations

from datetime import UTC, datetime

from eden.orchestrator._logging import LoopLogger
from eden.orchestrator.finalize._finalize import finalize_sandbox
from eden.providers._protocols import SandboxHandle
from eden.worktree._create import WorktreeHandle


def _utcnow() -> datetime:
    return datetime.now(UTC)


def finalize_loop_sandbox(
    *,
    handle: SandboxHandle | None,
    worktree: WorktreeHandle,
    agent_name: str,
    iteration_count: int,
    logger: LoopLogger | None,
) -> None:
    if handle is None:
        return
    finalize_sandbox(
        handle=handle,
        target_path=worktree.host_repo_path,
        agent_name=agent_name,
        iteration=iteration_count,
        timestamp=_utcnow,
        sink=logger.sink if logger is not None else None,
    )


__all__ = ["finalize_loop_sandbox"]
