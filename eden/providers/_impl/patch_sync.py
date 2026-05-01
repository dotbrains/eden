"""Snapshot / diff / apply for the isolated sandbox provider's patch-sync."""

from __future__ import annotations

import hashlib
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from eden.providers._types import FinalizeResult

_DEFAULT_IGNORE: tuple[str, ...] = (".git", ".eden")
_BUF_SIZE = 64 * 1024


@dataclass(frozen=True)
class DiffResult:
    added: frozenset[Path]
    changed: frozenset[Path]
    removed: frozenset[Path]


def snapshot(root: Path, *, ignore: tuple[str, ...] = _DEFAULT_IGNORE) -> dict[Path, str]:
    """Walk ``root`` and return ``{relative_path: sha256_hex}`` for every file.

    Top-level directories whose name is in ``ignore`` are skipped entirely.
    Symlinks are stored with their target paths included in the hash so a
    symlink retargeted to a different file produces a different hash.
    """
    out: dict[Path, str] = {}
    ignore_set = set(ignore)
    root = root.resolve()
    for current_dir, dirnames, filenames in os.walk(root, followlinks=False):
        rel_current = Path(current_dir).resolve().relative_to(root)
        at_root = rel_current == Path(".")
        if at_root:
            # Skip ignored names for both directories (e.g. .git dir in host
            # repos) and top-level files (e.g. .git file in git worktrees).
            dirnames[:] = [d for d in dirnames if d not in ignore_set]
            filenames = [f for f in filenames if f not in ignore_set]
        for name in filenames:
            full = Path(current_dir) / name
            # Use the entry's own path (not resolved) as the key so symlinks
            # appear under their own name rather than their target's name.
            rel = Path(current_dir).relative_to(root) / name
            try:
                if full.is_symlink():
                    target = os.readlink(full)
                    h = hashlib.sha256()
                    h.update(b"symlink:")
                    if isinstance(target, str):
                        h.update(target.encode("utf-8"))
                    else:
                        h.update(target)
                    out[rel] = h.hexdigest()
                else:
                    out[rel] = _hash_file(full)
            except FileNotFoundError:
                continue
    return out


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fp:
        for chunk in iter(lambda: fp.read(_BUF_SIZE), b""):
            h.update(chunk)
    return h.hexdigest()


def diff(*, before: dict[Path, str], after: dict[Path, str]) -> DiffResult:
    """Compute per-file change sets between two snapshots."""
    before_keys = set(before)
    after_keys = set(after)
    added = frozenset(after_keys - before_keys)
    removed = frozenset(before_keys - after_keys)
    changed = frozenset(p for p in (before_keys & after_keys) if before[p] != after[p])
    return DiffResult(added=added, changed=changed, removed=removed)


def apply(
    diff_result: DiffResult,
    *,
    src: Path,
    dst: Path,
) -> FinalizeResult:
    """Replay the diff against ``dst``.

    Adds and changes are copied from ``src`` to ``dst`` (parent dirs created).
    Removals unlink the file under ``dst`` (silent if already gone). Returns a
    summary; does NOT raise — individual file errors set ``applied=False``.
    """
    all_paths: list[Path] = sorted(diff_result.added | diff_result.changed | diff_result.removed)
    applied = True
    total_bytes = 0

    for rel in sorted(diff_result.added | diff_result.changed):
        src_file = src / rel
        dst_file = dst / rel
        try:
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            data = src_file.read_bytes()
            dst_file.write_bytes(data)
            total_bytes += len(data)
        except OSError as exc:
            print(f"[patch_sync] copy failed: {rel}: {exc}", file=sys.stderr)
            applied = False

    for rel in sorted(diff_result.removed):
        dst_file = dst / rel
        try:
            if dst_file.exists() or dst_file.is_symlink():
                dst_file.unlink()
        except FileNotFoundError:
            pass
        except OSError as exc:
            print(f"[patch_sync] unlink failed: {rel}: {exc}", file=sys.stderr)
            applied = False

    return FinalizeResult(
        applied=applied,
        files_changed=tuple(all_paths),
        patch_size_bytes=total_bytes,
    )


__all__ = ["DiffResult", "apply", "diff", "snapshot"]
