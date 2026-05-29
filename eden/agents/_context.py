"""IterationContext passed to Agent.build_command."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from eden.providers._protocols import SandboxHandle


@dataclass(frozen=True)
class IterationContext:
    iteration: int
    prompt: str
    sandbox_handle: SandboxHandle
    worktree_path: Path
    branch: str
    name: str | None
    resume_session: str | None = None
    fork_session: bool = False
    """When ``True``, agents that support session forking write a NEW
    session id while continuing from ``resume_session``'s captured state.
    Implies ``resume_session is not None``. Mirrors sandcastle's
    ``--fork-session`` (claude) / ``codex exec fork`` (codex) wiring
    (v0.6.6, 58f335f).
    """
