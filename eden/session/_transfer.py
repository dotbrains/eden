"""Cross-host session transfer helper.

Public-API wrapper around :func:`write_session_copy` for callers (CI
dashboards, multi-host orchestration scripts, manual operator tooling)
that need to move a captured session JSONL between machines while
rewriting embedded cwd paths.
"""

from __future__ import annotations

from pathlib import Path

from eden.errors import SessionCaptureFailed
from eden.session._store import write_session_copy


def transfer_session(
    *,
    source: Path,
    dest: Path,
    source_cwd: str,
    dest_cwd: str,
) -> Path:
    """Copy ``source`` JSONL to ``dest``, rewriting every absolute path that
    starts with ``source_cwd`` to start with ``dest_cwd`` instead.

    ``dest``'s parent directory is created if missing. Use this to migrate a
    captured session between host machines whose worktree paths differ
    (e.g. ``/Users/alice/repo`` → ``/home/build/repo``) so the resumed
    agent sees its own filesystem layout in the transcript.

    Returns the ``dest`` path. Raises :class:`SessionCaptureFailed` on I/O
    error.
    """
    if not source.is_file():
        raise SessionCaptureFailed(
            message=f"source session JSONL not found at {source}",
            hint="check the path is correct and readable",
        )
    try:
        write_session_copy(
            src=source,
            dest=dest,
            sandbox_prefix=source_cwd,
            host_prefix=dest_cwd,
        )
    except OSError as exc:
        raise SessionCaptureFailed(
            message=f"failed to transfer session to {dest}: {exc}",
            cause=exc,
        ) from exc
    return dest


__all__ = ["transfer_session"]
