"""Protocol types used by ``WorktreeHandle``."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from eden.worktree._git import _DEFAULT_GIT_TIMEOUT


class StatusPorcelain(Protocol):
    def __call__(self, *, repo_path: Path, timeout: float = _DEFAULT_GIT_TIMEOUT) -> str: ...


class WorktreeRemove(Protocol):
    def __call__(
        self,
        *,
        repo_path: Path,
        worktree_path: Path,
        timeout: float = _DEFAULT_GIT_TIMEOUT,
    ) -> None: ...


__all__ = ["StatusPorcelain", "WorktreeRemove"]
