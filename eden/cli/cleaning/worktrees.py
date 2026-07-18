"""Git worktree helpers for ``eden clean``."""

from __future__ import annotations

import subprocess
from pathlib import Path


def active_worktree_paths(repo: Path) -> set[Path]:
    """Return active git worktree paths, best-effort."""
    try:
        subprocess.run(
            ("git", "worktree", "prune"),
            cwd=str(repo),
            capture_output=True,
            text=True,
            check=False,
            timeout=60.0,
        )
        proc = subprocess.run(
            ("git", "worktree", "list", "--porcelain"),
            cwd=str(repo),
            capture_output=True,
            text=True,
            check=False,
            timeout=60.0,
        )
    except (OSError, subprocess.TimeoutExpired):
        return set()
    if proc.returncode != 0:
        return set()
    out: set[Path] = set()
    for line in proc.stdout.splitlines():
        if line.startswith("worktree "):
            out.add(Path(line[len("worktree ") :]).resolve())
    return out


__all__ = ["active_worktree_paths"]
