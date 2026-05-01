"""Derive Claude Code's ~/.claude/projects/<slug>/ directory name from a cwd path."""

from __future__ import annotations

from pathlib import PurePath


def claude_projects_slug(cwd: PurePath) -> str:
    """Return the Claude Code projects-dir slug for ``cwd``.

    Algorithm: take the path's string form, replace every '/', '\\', and ':'
    with '-', then strip trailing dashes. Adjacent separators (e.g., a Windows
    ``C:\\`` producing two adjacent characters that both map to '-') are
    preserved as adjacent dashes — the slug is reversible from the layout
    Claude Code uses on disk.
    """
    raw = str(cwd)
    slug = raw.replace("/", "-").replace("\\", "-").replace(":", "-")
    return slug.rstrip("-")
