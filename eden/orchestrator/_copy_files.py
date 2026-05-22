"""``copy_to_worktree`` — copy host-relative files into the worktree pre-boot.

Ports upstream's ``copyToWorktree`` option: each entry is a host-relative
file or directory path; the file is copied from ``source_root`` (the host
repo) into the freshly-carved worktree, preserving the relative path. Runs
**before** ``host.on_worktree_ready`` hooks fire so those hooks can use the
copied files.

Validation is strict (loud failure beats silent confusion):

* Paths must be relative and must not traverse outside ``source_root``
  (no ``..`` segments, no absolute paths) → :class:`InvalidOptions`.
* Missing sources raise :class:`CopyToWorktreeError` (not ``InvalidOptions``)
  so callers can distinguish "wrong API call" from "expected file isn't on
  disk yet".

Existing destinations are **overwritten** (files via ``shutil.copy2``, dirs
via ``copytree(dirs_exist_ok=True)``). This matches upstream's seeding
semantics: callers use ``copy_to_worktree`` to inject configs / secrets
that should replace whatever the carved worktree happens to contain.
"""

from __future__ import annotations

import shutil
from collections.abc import Sequence
from pathlib import Path, PurePosixPath

from eden.errors import CopyToWorktreeError, InvalidOptions


def _validate_entry(raw: str) -> PurePosixPath:
    """Normalise an entry and reject absolute / traversing paths."""
    if not isinstance(raw, str) or not raw:
        raise InvalidOptions(
            code="config.invalid_options",
            message=f"copy_to_worktree entries must be non-empty strings; got {raw!r}",
            hint="pass a list of host-relative paths like ['.env', 'fixtures/seed.json']",
        )
    p = PurePosixPath(raw)
    if p.is_absolute():
        raise InvalidOptions(
            code="config.invalid_options",
            message=(f"copy_to_worktree entry {raw!r} is absolute; entries must be host-relative"),
            hint="strip the leading slash or pass a path relative to cwd",
        )
    if any(part == ".." for part in p.parts):
        raise InvalidOptions(
            code="config.invalid_options",
            message=(
                f"copy_to_worktree entry {raw!r} contains '..'; entries must "
                "stay inside the host repo"
            ),
            hint="copy the file into the host repo first, then list its in-repo path",
        )
    return p


def apply_copy_to_worktree(
    *,
    paths: Sequence[str] | None,
    source_root: Path,
    worktree_path: Path,
) -> None:
    """Copy each ``paths`` entry from ``source_root`` into ``worktree_path``.

    No-op when ``paths`` is ``None`` or empty. No-op when source and worktree
    resolve to the same directory (the ``head`` branch strategy short-circuits
    before reaching this function, but the guard is cheap and defends against
    caller bugs).
    """
    if not paths:
        return
    # Validate every entry first so a bad path 5 entries deep fails before
    # we've already copied the first 4 — keeps callers from observing a
    # half-done copy.
    rels = [_validate_entry(raw) for raw in paths]
    try:
        same_root = source_root.resolve() == worktree_path.resolve()
    except OSError:
        # Resolve can fail on broken symlinks etc. — assume distinct and
        # let the copy raise a typed error below if needed.
        same_root = False
    if same_root:
        return

    for rel in rels:
        src = source_root / rel
        dst = worktree_path / rel
        if not src.exists():
            raise CopyToWorktreeError(
                code="copy.to_worktree_missing_source",
                message=f"copy_to_worktree source {str(rel)!r} does not exist under {source_root}",
                hint=(
                    "check the path is correct and relative to cwd; "
                    "absolute paths and '..' segments are rejected"
                ),
                source=src,
                target=dst,
            )
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)
        except OSError as exc:
            raise CopyToWorktreeError(
                message=f"copying {src} → {dst} failed: {exc}",
                hint="check disk space, permissions, and that the source is readable",
                cause=exc,
                source=src,
                target=dst,
            ) from exc


__all__ = ["apply_copy_to_worktree"]
