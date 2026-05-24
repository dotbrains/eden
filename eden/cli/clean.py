"""`eden clean` — purge stale ``.eden/`` runtime artifacts.

Deletes everything under ``.eden/{logs,sessions,worktrees,isolated}`` whose
mtime is older than ``--days`` (default: 7). With ``--all``, deletes those
subdirectories regardless of age. Refuses to touch ``.eden/`` itself or any
non-runtime files (Dockerfile, prompt.md, main.py, .env.example,
.gitignore — the scaffolded artifacts).
"""

from __future__ import annotations

import shutil
import time
from pathlib import Path

import typer
from rich.console import Console

console = Console(stderr=True)

# Subdirectories under ``.eden/`` that hold runtime artifacts (always safe to
# delete). The scaffolded files (Dockerfile, prompt.md, main.py, etc.) live
# directly under ``.eden/`` and are never touched.
_RUNTIME_DIRS = ("logs", "sessions", "worktrees", "isolated")


def _human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(size) < 1024.0:
            return f"{size:.1f}{unit}"
        size /= 1024.0
    return f"{size:.1f}PiB"


def _dir_size(path: Path) -> int:
    total = 0
    for child in path.rglob("*"):
        try:
            if child.is_file():
                total += child.stat().st_size
        except OSError:
            continue
    return total


def _delete_old(path: Path, *, cutoff: float) -> tuple[int, int]:
    """Delete files/dirs under ``path`` whose mtime is older than ``cutoff``.

    Returns ``(files_deleted, bytes_freed)``. The directory itself is left in
    place so the next run can re-create files into it.
    """
    files_deleted = 0
    bytes_freed = 0
    for child in sorted(path.iterdir(), key=lambda p: p.name):
        try:
            mtime = child.stat().st_mtime
        except OSError:
            continue
        if mtime >= cutoff:
            continue
        if child.is_dir() and not child.is_symlink():
            size = _dir_size(child)
            shutil.rmtree(child, ignore_errors=True)
            bytes_freed += size
            files_deleted += 1
        else:
            try:
                size = child.stat().st_size
                child.unlink()
                bytes_freed += size
                files_deleted += 1
            except OSError:
                continue
    return files_deleted, bytes_freed


def _delete_all(path: Path) -> tuple[int, int]:
    if not path.is_dir():
        return 0, 0
    size = _dir_size(path)
    count = sum(1 for _ in path.rglob("*"))
    shutil.rmtree(path, ignore_errors=True)
    return count, size


def clean_command(
    days: int = typer.Option(7, "--days", help="Delete artifacts older than N days"),
    all_: bool = typer.Option(False, "--all", help="Delete all runtime dirs regardless of age"),
    cwd: Path | None = typer.Option(None, "--cwd", help="Repo to clean"),  # noqa: B008
) -> None:
    """Delete stale .eden/{logs,sessions,worktrees,isolated} artifacts."""
    repo = (cwd or Path.cwd()).resolve()
    eden_dir_display = repo / ".eden"
    if not eden_dir_display.is_dir():
        console.print(f"[yellow]no .eden/ directory in {repo}[/yellow]")
        raise typer.Exit(code=0)
    # Resolve symlinks so the paths we hand to shutil.rmtree match git's
    # realpath-keyed worktree records (port of sandcastle PR #491 /
    # commit b6cc84f). Users who symlink .eden/ to a separate disk would
    # otherwise see stale-worktree cleanup mis-target. Keep the original
    # path around so user-facing output stays repo-relative.
    eden_dir = eden_dir_display.resolve()

    def _display(path: Path) -> str:
        try:
            return str(path.relative_to(repo))
        except ValueError:
            # .eden/ symlink targets a path outside the repo — show
            # absolute so the user can see where bytes were freed.
            return str(path)

    cutoff = time.time() - (days * 86400)
    total_files = 0
    total_bytes = 0
    for sub in _RUNTIME_DIRS:
        target = eden_dir / sub
        if not target.is_dir():
            continue
        if all_:
            files, freed = _delete_all(target)
        else:
            files, freed = _delete_old(target, cutoff=cutoff)
        if files > 0:
            scope = "all" if all_ else f">{days}d"
            console.print(f"  {_display(target)}: {files} entries, {_human_size(freed)} ({scope})")
        total_files += files
        total_bytes += freed

    if total_files == 0:
        console.print(f"[green]nothing to clean in {_display(eden_dir)}[/green]")
    else:
        console.print(f"[green]freed {_human_size(total_bytes)} ({total_files} entries)[/green]")
