"""Pure worktree state parsing and marker detection helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WorktreeRecord:
    path: Path
    branch: str | None  # None for detached HEAD


def parse_worktree_list(porcelain: str) -> tuple[WorktreeRecord, ...]:
    """Parse ``git worktree list --porcelain`` output into records."""
    out: list[WorktreeRecord] = []
    path: Path | None = None
    branch: str | None = None
    detached = False
    for raw in porcelain.splitlines():
        line = raw.rstrip()
        if not line:
            if path is not None:
                out.append(WorktreeRecord(path=path, branch=None if detached else branch))
            path, branch, detached = None, None, False
            continue
        if line.startswith("worktree "):
            path = Path(line[len("worktree ") :])
        elif line.startswith("branch refs/heads/"):
            branch = line[len("branch refs/heads/") :]
        elif line == "detached":
            detached = True
    if path is not None:
        out.append(WorktreeRecord(path=path, branch=None if detached else branch))
    return tuple(out)


IN_PROGRESS_MARKERS: tuple[str, ...] = (
    "rebase-merge",
    "rebase-apply",
    "MERGE_HEAD",
    "CHERRY_PICK_HEAD",
    "BISECT_LOG",
)


def detect_in_progress(*, repo_path: Path) -> Path | None:
    """Return the path to an in-progress git operation marker, or None."""
    git_dir = repo_path / ".git"
    if git_dir.is_file():
        try:
            text = git_dir.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        if text.startswith("gitdir: "):
            git_dir = Path(text[len("gitdir: ") :])
    if not git_dir.exists():
        return None
    for marker in IN_PROGRESS_MARKERS:
        path = git_dir / marker
        if path.exists():
            return path
    return None
