"""``copy_to_worktree`` — copy host-relative files into the worktree pre-boot.

Each entry is a host-relative file or directory path copied from
``source_root`` into the freshly-carved worktree before
``host.on_worktree_ready`` hooks fire. Validation is strict, and existing
destinations are overwritten to match the option's seeding semantics.
"""

from __future__ import annotations

import shutil
import time
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


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _resolve_confined_source(*, rel: PurePosixPath, src: Path, source_root: Path) -> Path:
    """Resolve ``src`` and reject symlinks that point outside ``source_root``."""
    resolved_root = source_root.resolve(strict=True)
    resolved_src = src.resolve(strict=True)
    if resolved_src != resolved_root and not _is_relative_to(resolved_src, resolved_root):
        raise InvalidOptions(
            code="config.invalid_options",
            message=(
                f"copy_to_worktree entry {str(rel)!r} resolves outside the host repo; "
                "entries must stay inside source_root even through symlinks"
            ),
            hint="copy the file into the host repo first, then list its in-repo path",
        )
    return resolved_src


def _raise_if_timed_out(
    *,
    started_at: float,
    timeout: float | None,
    source: Path,
    target: Path,
) -> None:
    if timeout is None or time.monotonic() - started_at <= timeout:
        return
    raise CopyToWorktreeError(
        code="copy.to_worktree_timeout",
        message=(
            f"copy_to_worktree did not complete within {timeout}s while copying "
            f"from {source} to {target}"
        ),
        hint="increase Timeouts.copy_to_worktree or reduce copy_to_worktree payload size",
        source=source,
        target=target,
        timeout=timeout,
        timed_out=True,
    )


def apply_copy_to_worktree(
    *,
    paths: Sequence[str] | None,
    source_root: Path,
    worktree_path: Path,
    timeout: float | None = 60.0,
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

    started_at = time.monotonic()
    for rel in rels:
        _raise_if_timed_out(
            started_at=started_at,
            timeout=timeout,
            source=source_root,
            target=worktree_path,
        )
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
            resolved_src = _resolve_confined_source(rel=rel, src=src, source_root=source_root)
            dst.parent.mkdir(parents=True, exist_ok=True)
            if resolved_src.is_dir():
                shutil.copytree(resolved_src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(resolved_src, dst)
            _raise_if_timed_out(
                started_at=started_at,
                timeout=timeout,
                source=source_root,
                target=worktree_path,
            )
        except OSError as exc:
            raise CopyToWorktreeError(
                message=f"copying {src} → {dst} failed: {exc}",
                hint="check disk space, permissions, and that the source is readable",
                cause=exc,
                source=src,
                target=dst,
            ) from exc


__all__ = ["apply_copy_to_worktree"]
