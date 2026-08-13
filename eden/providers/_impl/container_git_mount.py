"""Resolve the git common dir a linked worktree's ``.git`` file points at.

Docker/Podman bind-mount only ``worktree_path`` into the container. When
``worktree_path`` is a linked worktree (created via ``git worktree add`` for
the ``merge_to_head``/``named`` branch strategies — the default for
bind-mount providers), its ``.git`` is a *file* holding an absolute host path
to the main repository's private worktree metadata dir
(``<host_repo>/.git/worktrees/<branch>``). That path is unreachable inside
the container unless the main repository's git dir is bind-mounted too, so
every git command against the mounted worktree fails with
``fatal: not a git repository``.

This module handles the Linux/macOS case, where the ``gitdir:`` pointer is a
POSIX path: mounting the resolved common dir at its own host path (an
identity mount) is enough — confirmed against a real Docker container
(``docs/adr/0016-linked-worktree-git-dir-mount.md``). Windows hosts write a
``C:\\...`` pointer a Linux container can't parse regardless of mount
layout; that case needs a different fix and lives in
``container_git_mount_windows.py``.
"""

from __future__ import annotations

import re
from pathlib import Path

_GITDIR_PREFIX = "gitdir:"
_WINDOWS_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]")


def _read_gitdir_pointer(worktree_path: Path) -> str | None:
    git_path = worktree_path / ".git"
    if not git_path.is_file():
        return None
    contents = git_path.read_text(encoding="utf-8").strip()
    if not contents.startswith(_GITDIR_PREFIX):
        return None
    return contents[len(_GITDIR_PREFIX) :].strip()


def looks_windows_shaped(raw_path: str) -> bool:
    """Detect a Windows-style absolute path by string shape alone.

    Deliberately does **not** go through ``container_mounts._is_windows_host_path``
    (which takes a ``Path``): on a real Windows host, ``Path`` is
    ``WindowsPath``, and ``str(WindowsPath(some_string))`` normalizes *any*
    rooted path to backslash form regardless of the string's original
    separators — so wrapping a content string in ``Path`` first before
    checking its shape would make this spuriously true for genuinely
    POSIX-shaped strings whenever this code happens to run on Windows,
    which is exactly the platform it needs to classify correctly.
    """
    return bool(_WINDOWS_PATH_RE.match(raw_path)) or "\\" in raw_path


def resolve_git_common_dir(worktree_path: Path) -> Path | None:
    """Return the git dir to additionally bind-mount, or ``None`` if none is needed.

    Returns ``None`` when ``worktree_path/.git`` is already a real directory
    — the ``head`` strategy, where ``worktree_path`` equals the host
    repository and its ``.git`` dir is mounted as part of the worktree mount
    itself — when ``worktree_path`` doesn't look like a git checkout at all
    (e.g. in unit tests that pass a bare temp dir), or when the ``gitdir:``
    pointer is Windows-shaped (handled instead by
    ``container_git_mount_windows.resolve_windows_git_mounts``).

    The returned path is mounted at its own absolute host path (an identity
    mount), which is what lets the ``gitdir:`` pointer inside the mounted
    worktree resolve correctly inside the container on Linux/macOS, where
    host and sandbox paths share the same POSIX format.
    """
    git_path = worktree_path / ".git"
    if git_path.is_dir():
        return None

    raw = _read_gitdir_pointer(worktree_path)
    if raw is None or looks_windows_shaped(raw):
        return None

    private_dir = Path(raw)
    if not private_dir.is_absolute():
        private_dir = (worktree_path / private_dir).resolve()

    commondir_file = private_dir / "commondir"
    if commondir_file.is_file():
        common_raw = commondir_file.read_text(encoding="utf-8").strip()
        common_dir = (private_dir / common_raw).resolve()
    else:
        common_dir = private_dir.resolve()
    if not common_dir.is_dir():
        return None
    return common_dir


__all__ = ["looks_windows_shaped", "resolve_git_common_dir"]
