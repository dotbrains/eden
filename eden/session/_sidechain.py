"""Claude sidechain transcript capture helpers."""

from __future__ import annotations

import json
from pathlib import Path

from eden.session._branch import sanitize_branch
from eden.session._slug import claude_projects_slug
from eden.session._store import write_session_copy


def _is_sidechain_transcript(path: Path) -> bool:
    """True if any JSONL entry in ``path`` is a Claude subagent line."""
    try:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                if '"isSidechain"' not in line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict) and obj.get("isSidechain") is True:
                    return True
    except (OSError, UnicodeDecodeError):
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
    """Capture Claude subagent/workflow transcripts stored as separate files."""
    home_path = home if home is not None else Path.home()
    slug = claude_projects_slug(sandbox_cwd)
    slug_dir = home_path / ".claude" / "projects" / slug
    if not slug_dir.is_dir():
        return []
    safe_branch = sanitize_branch(branch)
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


__all__ = ["capture_sidechain_sessions"]
