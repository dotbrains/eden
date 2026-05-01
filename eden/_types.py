"""Shared frozen dataclasses for eden's public result surface.

Convention: every type here is a ``@dataclass(frozen=True)``. ``frozen``
prevents attribute reassignment on the dataclass itself; it does NOT make
contained collections (``list``, ``dict``) read-only. Callers should treat
the contained ``iterations``, ``commits``, and ``env`` collections on
``RunResult`` as snapshots — eden never mutates them after construction
and consumers should not either.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Usage:
    input_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class Commit:
    sha: str


@dataclass(frozen=True)
class Iteration:
    index: int
    completion_signal: str | None
    session_id: str | None
    session_file_path: Path | None
    usage: Usage | None


@dataclass(frozen=True)
class Timeouts:
    hook_step: float = 60.0
    iteration_step: float | None = None


@dataclass(frozen=True)
class RunResult:
    iterations: list[Iteration]
    completion_signal: str | None
    branch: str
    stdout: str
    commits: list[Commit]
    worktree_path: Path
    preserved_worktree_path: Path | None
    merged_to_target_branch: str | None
    cwd: Path
    prompt: str
    env: dict[str, str]
    log_file_path: Path | None
    session_id: str | None
    session_file_path: Path | None
    usage: Usage | None
