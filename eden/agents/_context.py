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
