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
"""

from __future__ import annotations

from pathlib import Path

from eden.providers._impl.container_mounts import _is_windows_host_path

_GITDIR_PREFIX = "gitdir:"


def resolve_git_common_dir(worktree_path: Path) -> Path | None:
    """Return the git dir to additionally bind-mount, or ``None`` if none is needed.

    Returns ``None`` when ``worktree_path/.git`` is already a real directory
    — the ``head`` strategy, where ``worktree_path`` equals the host
    repository and its ``.git`` dir is mounted as part of the worktree mount
    itself — or when ``worktree_path`` doesn't look like a git checkout at
    all (e.g. in unit tests that pass a bare temp dir).

    The returned path is mounted at its own absolute host path (an identity
    mount), which is what lets the ``gitdir:`` pointer inside the mounted
    worktree resolve correctly inside the container — but only on Linux/macOS,
    where host and sandbox paths share the same POSIX format. On Windows the
    ``gitdir:`` pointer itself is a ``C:\\...`` path that a Linux container
    can't parse regardless of mount layout, and a mount *target* in that
    shape would fail container startup outright, so this returns ``None``
    there rather than trade a git-command failure for a container-start
    failure. Docker/Podman are documented as Linux/macOS providers, so this
    covers eden's supported case.
    """
    git_path = worktree_path / ".git"
    if git_path.is_dir():
        return None
    if not git_path.is_file():
        return None

    contents = git_path.read_text(encoding="utf-8").strip()
    if not contents.startswith(_GITDIR_PREFIX):
        return None

    private_dir_raw = contents[len(_GITDIR_PREFIX) :].strip()
    private_dir = Path(private_dir_raw)
    if not private_dir.is_absolute():
        private_dir = (worktree_path / private_dir).resolve()

    commondir_file = private_dir / "commondir"
    if commondir_file.is_file():
        common_raw = commondir_file.read_text(encoding="utf-8").strip()
        common_dir = (private_dir / common_raw).resolve()
    else:
        common_dir = private_dir.resolve()
    if not common_dir.is_dir() or _is_windows_host_path(common_dir):
        return None
    return common_dir


__all__ = ["resolve_git_common_dir"]
