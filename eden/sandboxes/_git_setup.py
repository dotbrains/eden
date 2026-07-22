"""Sandbox-side git setup shared by run/create_sandbox/interactive."""

from __future__ import annotations

import shlex
from pathlib import Path

from eden.providers._protocols import SandboxHandle


def _normalize_git_path(value: str) -> str:
    return value.replace("\\", "/").rstrip("/")


def ensure_git_safe_directory(
    handle: SandboxHandle,
    *,
    timeout: float,
) -> None:
    """Mark the sandbox worktree safe for git if it is not already configured."""
    worktree_path: Path = handle.worktree_path
    target = _normalize_git_path(worktree_path.as_posix())
    current = handle.exec(
        "git config --global --get-all safe.directory || true",
        timeout=timeout,
    )
    configured = {_normalize_git_path(line.strip()) for line in current.stdout.splitlines()}
    if target in configured:
        return

    result = handle.exec(
        f"git config --global --add safe.directory {shlex.quote(worktree_path.as_posix())}",
        timeout=timeout,
    )
    if result.exit_code != 0:
        raise RuntimeError(f"failed to configure git safe.directory: {result.stderr.strip()}")


__all__ = ["ensure_git_safe_directory"]
