"""Thin wrappers around git commands the worktree manager runs."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from eden.worktree.errors import GitCommandFailed, WorktreeCollision


def _run_git(argv: tuple[str, ...], *, cwd: Path) -> tuple[str, str]:
    proc = subprocess.run(
        argv,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise GitCommandFailed(argv=argv, exit_code=proc.returncode, stderr=proc.stderr)
    return proc.stdout, proc.stderr


def status_porcelain(*, repo_path: Path) -> str:
    stdout, _ = _run_git(("git", "status", "--porcelain"), cwd=repo_path)
    return stdout


def branch_exists(*, repo_path: Path, branch: str) -> bool:
    proc = subprocess.run(
        ("git", "rev-parse", "--verify", f"refs/heads/{branch}"),
        cwd=str(repo_path),
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode == 0


@dataclass(frozen=True)
class _WorktreeRecord:
    path: Path
    branch: str | None  # None for detached HEAD


def _parse_worktree_list(porcelain: str) -> tuple[_WorktreeRecord, ...]:
    """Parse ``git worktree list --porcelain`` output into records.

    Each record is a paragraph of ``key value`` lines separated by blanks.
    Lines we care about: ``worktree <path>`` and ``branch refs/heads/<n>``;
    a ``detached`` line marks a detached-HEAD checkout.
    """
    out: list[_WorktreeRecord] = []
    path: Path | None = None
    branch: str | None = None
    detached = False
    for raw in porcelain.splitlines():
        line = raw.rstrip()
        if not line:
            if path is not None:
                out.append(_WorktreeRecord(path=path, branch=None if detached else branch))
            path, branch, detached = None, None, False
            continue
        if line.startswith("worktree "):
            path = Path(line[len("worktree ") :])
        elif line.startswith("branch refs/heads/"):
            branch = line[len("branch refs/heads/") :]
        elif line == "detached":
            detached = True
    if path is not None:
        out.append(_WorktreeRecord(path=path, branch=None if detached else branch))
    return tuple(out)


def list_worktrees(*, repo_path: Path) -> tuple[_WorktreeRecord, ...]:
    """Return every worktree git knows about for ``repo_path``."""
    stdout, _ = _run_git(("git", "worktree", "list", "--porcelain"), cwd=repo_path)
    return _parse_worktree_list(stdout)


_IN_PROGRESS_MARKERS: tuple[str, ...] = (
    "rebase-merge",
    "rebase-apply",
    "MERGE_HEAD",
    "CHERRY_PICK_HEAD",
    "BISECT_LOG",
)


def _detect_in_progress(*, repo_path: Path) -> Path | None:
    """Return the path to an in-progress git operation marker, or None.

    ``git worktree add`` does not refuse outright in mid-rebase, but the
    resulting state confuses everything downstream (the new worktree's
    HEAD inherits the partially-rewritten state). We surface a clear
    error instead.
    """
    git_dir = repo_path / ".git"
    if git_dir.is_file():
        # We're in a worktree ourselves; resolve the gitdir pointer.
        try:
            text = git_dir.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        if text.startswith("gitdir: "):
            git_dir = Path(text[len("gitdir: ") :])
    if not git_dir.exists():
        return None
    for marker in _IN_PROGRESS_MARKERS:
        path = git_dir / marker
        if path.exists():
            return path
    return None


def _check_collisions(*, repo_path: Path, branch: str) -> None:
    """Raise WorktreeCollision if ``git worktree add`` would conflict.

    Two conditions are detected up front so the caller sees a structured
    error rather than a cryptic git stderr dump:

    * the host repo is mid-rebase / mid-merge / mid-cherry-pick;
    * the target ``branch`` is already checked out by another worktree.
    """
    in_progress = _detect_in_progress(repo_path=repo_path)
    if in_progress is not None:
        raise WorktreeCollision(
            branch=branch,
            reason="rebase_in_progress",
            conflict_path=in_progress,
            hint=(
                "finish or abort the in-flight git operation before carving a new "
                "worktree (`git rebase --abort` / `git merge --abort` / "
                "`git cherry-pick --abort`)."
            ),
        )
    for record in list_worktrees(repo_path=repo_path):
        if record.branch == branch:
            raise WorktreeCollision(
                branch=branch,
                reason="branch_in_use",
                conflict_path=record.path,
                hint=(
                    f"branch {branch!r} is already checked out at {record.path}; "
                    "remove that worktree or pick a different branch."
                ),
            )


def worktree_add(
    *,
    repo_path: Path,
    worktree_path: Path,
    branch: str,
    base: str,
) -> None:
    _check_collisions(repo_path=repo_path, branch=branch)
    _run_git(
        (
            "git",
            "worktree",
            "add",
            "-b",
            branch,
            str(worktree_path),
            base,
        ),
        cwd=repo_path,
    )


def worktree_remove(*, repo_path: Path, worktree_path: Path) -> None:
    _run_git(
        ("git", "worktree", "remove", "--force", str(worktree_path)),
        cwd=repo_path,
    )
