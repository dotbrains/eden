"""Session JSONL capture: locate Claude Code's transcript, copy + rewrite paths."""

from __future__ import annotations

import json
from pathlib import Path

from eden.errors import SessionCaptureFailed
from eden.session._branch import sanitize_branch as _sanitize_branch
from eden.session._slug import claude_projects_slug
from eden.session._store import write_session_copy


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
        # ``sandbox_cwd.as_posix()`` keeps the prefix in forward-slash form so
        # paths emitted by Linux-container Claude Code (always POSIX) still
        # match when Eden runs on a Windows host (where ``str(Path("/workspace"))``
        # would be ``"\\workspace"``).
        write_session_copy(
            src=src,
            dest=dest,
            sandbox_prefix=sandbox_cwd.as_posix(),
            host_prefix=str(host_repo_path),
        )
    except OSError as exc:
        raise SessionCaptureFailed(
            message=f"failed to write session copy to {dest}: {exc}",
            cause=exc,
        ) from exc
    return dest


def _is_sidechain_transcript(path: Path) -> bool:
    """True if any JSONL entry in ``path`` is a Claude subagent (sidechain)
    line (``"isSidechain": true``).

    Reads lazily and short-circuits on the first match. The cheap substring
    pre-filter skips JSON parsing for the overwhelming majority of lines
    (transcripts carry one ``isSidechain`` field per entry, usually ``false``).
    """
    try:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                if '"isSidechain"' not in line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if obj.get("isSidechain") is True:
                    return True
    except OSError:
        return False
    return False


def capture_sidechain_sessions(
    *,
    main_session_id: str,
    sandbox_cwd: Path,
    host_repo_path: Path,
    branch: str,
    iteration: int,
    since: float | None = None,
    home: Path | None = None,
) -> list[Path]:
    """Capture Claude subagent/workflow transcripts stored as *separate*
    session files in the same project slug dir.

    Each match is copied + path-rewritten next to the main session as
    ``.eden/sessions/<branch>/iter-<iteration>-sub-<id>.jsonl`` (so
    ``eden replay`` and the ``iter-<n>-*`` globs pick it up). A sidechain file
    is any sibling ``.jsonl`` other than the main session that carries at least
    one ``isSidechain: true`` entry.

    ``since`` (the agent's start time, epoch seconds) scopes the sweep to this
    run: only files modified at/after it are captured, so a sandbox slug shared
    across runs (e.g. a fixed ``/workspace`` cwd under Docker) doesn't drag in
    subagent transcripts left by earlier runs. ``None`` disables the time
    filter.

    Best-effort: a missing slug dir, unreadable file, or failed copy is skipped,
    never raised — a partial subagent census must not sink an otherwise-good
    run. Inline sidechain entries (subagents recorded *within* the main
    transcript) need no handling here; they're already in the main capture.
    This covers the separate-file case, notably isolated/cloud providers where
    only the main session is otherwise pulled back to the host. Mirrors
    sandcastle's subagent/workflow transcript capture (v0.9.0).
    """
    home_path = home if home is not None else Path.home()
    slug = claude_projects_slug(sandbox_cwd)
    slug_dir = home_path / ".claude" / "projects" / slug
    if not slug_dir.is_dir():
        return []
    safe_branch = _sanitize_branch(branch)
    captured: list[Path] = []
    for src in sorted(slug_dir.glob("*.jsonl")):
        if src.stem == main_session_id:
            continue
        try:
            if since is not None and src.stat().st_mtime < since:
                continue
        except OSError:
            continue
        if not _is_sidechain_transcript(src):
            continue
        dest = (
            host_repo_path
            / ".eden"
            / "sessions"
            / safe_branch
            / f"iter-{iteration}-sub-{src.stem}.jsonl"
        )
        try:
            write_session_copy(
                src=src,
                dest=dest,
                sandbox_prefix=sandbox_cwd.as_posix(),
                host_prefix=str(host_repo_path),
            )
        except OSError:
            continue
        captured.append(dest)
    return captured


def _default_claude_session_storage() -> object:
    """Late-bound import of :class:`ClaudeSessionStorage`.

    Avoids the module-load cycle ``eden.session.__init__`` →
    ``eden.session._claude`` → ``eden.session.capture_session``.
    """
    from eden.session._claude import ClaudeSessionStorage

    return ClaudeSessionStorage()


# Re-export per-agent SessionStorage implementations + the cross-host
# transfer helper so downstream tooling (CI dashboards, multi-host
# orchestration) can move sessions without poking at private modules.
from eden.session._claude import ClaudeSessionStorage  # noqa: E402
from eden.session._codex import (  # noqa: E402
    CodexSessionStorage,
    find_codex_session_path,
)
from eden.session._transfer import transfer_session  # noqa: E402

__all__ = [
    "ClaudeSessionStorage",
    "CodexSessionStorage",
    "capture_session",
    "capture_sidechain_sessions",
    "find_codex_session_path",
    "transfer_session",
]
