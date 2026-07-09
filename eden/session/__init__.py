"""Session JSONL capture: locate Claude Code's transcript, copy + rewrite paths."""

from __future__ import annotations

from pathlib import Path, PurePath

from eden.errors import SessionCaptureFailed
from eden.session._branch import sanitize_branch as _sanitize_branch
from eden.session._sidechain import capture_sidechain_sessions
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


def _default_claude_session_storage() -> object:
    """Late-bound import of :class:`ClaudeSessionStorage`.

    Avoids the module-load cycle ``eden.session.__init__`` →
    ``eden.session._claude`` → ``eden.session.capture_session``.
    """
    from eden.session._claude import ClaudeSessionStorage

    return ClaudeSessionStorage()


def encode_project_path(cwd: PurePath | str) -> str:
    """Return the Claude Code project slug for ``cwd``."""
    return claude_projects_slug(PurePath(cwd) if isinstance(cwd, str) else cwd)


def claude_host_session_path(
    cwd: PurePath | str,
    session_id: str,
    *,
    projects_dir: Path | None = None,
) -> Path:
    """Return the expected host-side Claude Code session JSONL path."""
    base = projects_dir if projects_dir is not None else Path.home() / ".claude" / "projects"
    return base / encode_project_path(cwd) / f"{session_id}.jsonl"


def claude_sandbox_session_path(
    cwd: PurePath | str,
    session_id: str,
    *,
    projects_dir: PurePath | str,
) -> PurePath:
    """Return the sandbox-side Claude Code session JSONL path."""
    base = PurePath(projects_dir)
    return base / encode_project_path(cwd) / f"{session_id}.jsonl"


def find_claude_session_on_host(
    session_id: str,
    *,
    projects_dir: Path | None = None,
) -> Path | None:
    """Scan ``projects_dir`` for ``<session_id>.jsonl`` and return the first match."""
    root = projects_dir if projects_dir is not None else Path.home() / ".claude" / "projects"
    if not root.is_dir():
        return None
    try:
        entries = sorted(root.iterdir())
    except OSError:
        return None
    for entry in entries:
        try:
            if not entry.is_dir():
                continue
            candidate = entry / f"{session_id}.jsonl"
            if candidate.is_file():
                return candidate
        except OSError:
            continue
    return None


def find_codex_session_on_host(
    session_id: str,
    *,
    sessions_dir: Path | None = None,
) -> Path | None:
    """Scan Codex's host sessions tree for ``session_id``."""
    root = sessions_dir if sessions_dir is not None else Path.home() / ".codex" / "sessions"
    return find_codex_session_path(root, session_id)


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
    "claude_host_session_path",
    "claude_sandbox_session_path",
    "encode_project_path",
    "find_claude_session_on_host",
    "find_codex_session_on_host",
    "find_codex_session_path",
    "transfer_session",
]
