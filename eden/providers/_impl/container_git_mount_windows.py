"""Windows fix for the linked-worktree git-mount problem.

See ``container_git_mount.py`` for the Linux/macOS case and background.
Windows writes a ``C:\\...`` ``gitdir:`` pointer that a Linux container
can't parse regardless of mount layout, so the identity-mount trick doesn't
work there. This ports the technique Sandcastle's
``0006-git-worktree-mounts-on-windows.md`` ADR documents: mount the parent
git dir at a deterministic in-container path, and overlay a corrected
``.git`` file whose pointer uses that path.

**This has not been exercised against a real Windows host + Docker
Desktop/Podman pairing** (no such environment was available while writing
it) — treat it as best-effort until someone verifies it there. The pure
planning logic (``plan_windows_git_mounts``) is unit-tested on every
platform; the filesystem/mount wiring around it (``resolve_windows_git_mounts``)
is only exercised with a hand-written fake ``.git`` file, since a real
Windows-style linked worktree can't be produced by ``git worktree add`` on
a non-Windows CI runner.
"""

from __future__ import annotations

from pathlib import Path, PureWindowsPath

from eden.providers._impl.container_git_mount import _read_gitdir_pointer, looks_windows_shaped
from eden.providers._impl.container_mounts import SANDBOX_WORKDIR
from eden.providers._types import Mount

_GITDIR_PREFIX = "gitdir:"

SANDBOX_PARENT_GIT_DIR = Path("/.eden-parent-git")
"""Deterministic in-container mount point for a Windows host's parent git
dir. Reserved — providers and container images should not use this path
for anything else."""


def plan_windows_git_mounts(raw_gitdir_pointer: str) -> tuple[str, str] | None:
    """Pure planning step for the Windows linked-worktree git-mount fix.

    Given the raw ``gitdir:`` pointer content, return
    ``(parent_git_dir, corrected_gitfile_content)``, or ``None`` if the
    pointer isn't Windows-shaped. No filesystem access, so this is safe (and
    exercised) on every host OS regardless of where the fix itself runs.

    Assumes the standard linked-worktree layout eden always creates via
    ``git worktree add`` against a non-worktree main repository:
    ``<parent_git_dir>\\worktrees\\<name>``. ``parent_git_dir`` is derived
    structurally (strip ``worktrees`` and ``<name>``) rather than by reading
    the private dir's ``commondir`` file, which would need a real Windows
    filesystem to verify.
    """
    if not looks_windows_shaped(raw_gitdir_pointer):
        return None
    private_dir = PureWindowsPath(raw_gitdir_pointer)
    parent_git_dir = str(private_dir.parent.parent)
    corrected_content = (
        f"{_GITDIR_PREFIX} {SANDBOX_PARENT_GIT_DIR.as_posix()}/worktrees/{private_dir.name}\n"
    )
    return parent_git_dir, corrected_content


def resolve_windows_git_mounts(worktree_path: Path) -> tuple[Mount, Mount] | None:
    """Return the two mounts a Windows-hosted linked worktree needs, or ``None``.

    Writes a corrected ``.git`` file next to ``worktree_path`` (inside
    eden's own ``.eden/worktrees/`` dir, never inside the worktree itself)
    whose ``gitdir:`` pointer uses ``SANDBOX_PARENT_GIT_DIR`` — a path a
    Linux container can resolve — then returns mounts for:

    1. The real parent git dir, at ``SANDBOX_PARENT_GIT_DIR``.
    2. The corrected ``.git`` file, overriding the original ``.git`` file
       the worktree mount would otherwise present at
       ``SANDBOX_WORKDIR/.git``.

    See the module docstring: this is unverified on a real Windows host.
    """
    raw = _read_gitdir_pointer(worktree_path)
    if raw is None:
        return None
    planned = plan_windows_git_mounts(raw)
    if planned is None:
        return None
    parent_git_dir_raw, corrected_content = planned

    corrected_path = worktree_path.parent / f"{worktree_path.name}.git-windows"
    corrected_path.write_text(corrected_content, encoding="utf-8")

    return (
        Mount(host=Path(parent_git_dir_raw), sandbox=SANDBOX_PARENT_GIT_DIR),
        Mount(host=corrected_path, sandbox=SANDBOX_WORKDIR / ".git"),
    )


def merge_windows_git_mounts(mount_map: dict[Path, Mount], worktree_path: Path) -> frozenset[Mount]:
    """Add ``resolve_windows_git_mounts`` output to ``mount_map`` in place.

    Returns the mounts that were added (empty if none applied), so the
    caller can skip its ``/home/agent`` file-mount-parent prep step for
    them — their parents (``SANDBOX_WORKDIR``, ``SANDBOX_PARENT_GIT_DIR``)
    are already handled by the primary worktree mount and Docker/Podman's
    own directory-mount auto-creation, not eden's parent-prep exec.
    """
    windows_mounts = resolve_windows_git_mounts(worktree_path)
    if windows_mounts is None:
        return frozenset()
    for mount in windows_mounts:
        mount_map[mount.sandbox] = mount
    return frozenset(windows_mounts)


__all__ = [
    "SANDBOX_PARENT_GIT_DIR",
    "merge_windows_git_mounts",
    "plan_windows_git_mounts",
    "resolve_windows_git_mounts",
]
