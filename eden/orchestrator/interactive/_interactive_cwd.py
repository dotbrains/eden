"""CWD resolution for interactive sessions."""

from __future__ import annotations

from pathlib import Path

from eden.errors import CwdError
from eden.worktree._create import WorktreeHandle


def resolve_interactive_cwd(
    *,
    existing_worktree: WorktreeHandle | None,
    cwd: str | Path | None,
) -> Path:
    """Resolve and validate the host repository path for ``interactive()``."""
    cwd_path = (
        existing_worktree.host_repo_path
        if existing_worktree is not None
        else Path(cwd)
        if cwd is not None
        else Path.cwd()
    )
    if not cwd_path.exists() or not cwd_path.is_dir():
        raise CwdError(message=f"cwd does not exist or is not a directory: {cwd_path}")
    if not (cwd_path / ".git").exists():
        raise CwdError(
            message=f"cwd is not a git repository: {cwd_path}",
            hint="run `git init` or pass a different cwd",
        )
    return cwd_path


__all__ = ["resolve_interactive_cwd"]
