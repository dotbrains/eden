"""Session JSONL capture: locate Claude Code's transcript, copy + rewrite paths."""

from __future__ import annotations

import re
from pathlib import Path

from eden.errors import SessionCaptureFailed
from eden.session._slug import claude_projects_slug
from eden.session._store import write_session_copy

# Mirrors eden.logging._file._BRANCH_SANITIZE for consistency.
_BRANCH_SANITIZE = re.compile(r"[^A-Za-z0-9._-]+")
_BRANCH_MAX = 64


def _sanitize_branch(branch: str) -> str:
    safe = _BRANCH_SANITIZE.sub("-", branch).strip("-")
    if not safe:
        safe = "run"
    if len(safe) > _BRANCH_MAX:
        safe = safe[:_BRANCH_MAX]
    return safe


def capture_session(
    *,
    session_id: str,
    sandbox_cwd: Path,
    host_repo_path: Path,
    branch: str,
    iteration: int,
    home: Path | None = None,
) -> Path:
    """Locate ``~/.claude/projects/<slug>/<session_id>.jsonl`` and copy it to
    ``<host_repo_path>/.eden/sessions/<sanitized-branch>/iter-<iteration>-<session_id>.jsonl``,
    rewriting absolute paths from ``str(sandbox_cwd)`` -> ``str(host_repo_path)``.

    Returns the destination path. Raises ``SessionCaptureFailed`` on any failure.
    """
    home_path = home if home is not None else Path.home()
    slug = claude_projects_slug(sandbox_cwd)
    src = home_path / ".claude" / "projects" / slug / f"{session_id}.jsonl"
    if not src.is_file():
        raise SessionCaptureFailed(
            message=f"Claude Code session JSONL not found at {src}",
            hint="check that Claude Code wrote a session file for the slug",
        )
    safe_branch = _sanitize_branch(branch)
    dest = (
        host_repo_path / ".eden" / "sessions" / safe_branch / f"iter-{iteration}-{session_id}.jsonl"
    )
    try:
        write_session_copy(
            src=src,
            dest=dest,
            sandbox_prefix=str(sandbox_cwd),
            host_prefix=str(host_repo_path),
        )
    except OSError as exc:
        raise SessionCaptureFailed(
            message=f"failed to write session copy to {dest}: {exc}",
            cause=exc,
        ) from exc
    return dest


__all__ = ["capture_session"]
