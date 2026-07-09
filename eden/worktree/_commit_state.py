"""Commit census and branch refresh helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from eden.worktree.errors import GitCommandFailed, GitCommandTimeout


class RunGit(Protocol):
    def __call__(self, argv: tuple[str, ...], *, cwd: Path, timeout: float) -> tuple[str, str]: ...


def _symbolic_head(*, run_git: RunGit, repo_path: Path, timeout: float) -> str | None:
    """Return the branch HEAD points at, or ``None`` when detached.

    ``git symbolic-ref --quiet HEAD`` exits non-zero on a detached HEAD; we
    map both that and any timeout to ``None`` so callers treat them the same
    as "not on a branch".
    """
    try:
        stdout, _ = run_git(
            ("git", "symbolic-ref", "--quiet", "HEAD"), cwd=repo_path, timeout=timeout
        )
    except (GitCommandFailed, GitCommandTimeout):
        return None
    ref = stdout.strip()
    prefix = "refs/heads/"
    return ref[len(prefix) :] if ref.startswith(prefix) else None


def _rev_parse_head(*, run_git: RunGit, repo_path: Path, timeout: float) -> str:
    try:
        stdout, _ = run_git(("git", "rev-parse", "HEAD"), cwd=repo_path, timeout=timeout)
    except (GitCommandFailed, GitCommandTimeout):
        return ""
    return stdout.strip()


def head_sha(*, run_git: RunGit, repo_path: Path, timeout: float) -> str:
    """Return ``repo_path``'s current HEAD SHA, or ``""`` if it can't be read.

    The run loop snapshots this immediately after carving the worktree and
    before the agent runs, so the SHA marks the commit census baseline. An
    unborn branch, detached/garbage HEAD, or timed-out git maps to ``""`` -
    :func:`new_commits` treats that as "no baseline" and reports no commits
    rather than raising.
    """
    return _rev_parse_head(run_git=run_git, repo_path=repo_path, timeout=timeout)


def new_commits(
    *, run_git: RunGit, worktree_path: Path, base_sha: str, timeout: float
) -> tuple[str, ...]:
    """Return SHAs committed on the worktree's branch since ``base_sha``.

    Runs ``git rev-list <base_sha>..HEAD`` in ``worktree_path`` to list the
    commits the agent created during this run, newest first. The run loop
    bounds it with ``Timeouts.commit_collection``.

    Best-effort by design: an empty ``base_sha`` (HEAD was unreadable at run
    start), an invalid ref, or a timed-out git all return ``()`` rather than
    raising - a failed commit census must never sink an otherwise-good run.
    Bind-mount providers (no-sandbox/docker/podman) preserve the agent's
    commits on the branch, so this yields real SHAs; isolated/cloud providers
    patch-sync file changes only, leaving the host worktree with no new
    commits, so an empty result there is correct, not a failure.
    """
    if not base_sha:
        return ()
    try:
        stdout, _ = run_git(
            ("git", "rev-list", f"{base_sha}..HEAD"),
            cwd=worktree_path,
            timeout=timeout,
        )
    except (GitCommandFailed, GitCommandTimeout):
        return ()
    return tuple(line.strip() for line in stdout.splitlines() if line.strip())


def refresh_from_origin(
    *,
    run_git: RunGit,
    no_config_lock_flags: tuple[str, ...],
    worktree_path: Path,
    branch: str,
    timeout: float,
) -> None:
    """Fast-forward a reused, clean worktree to ``origin/<branch>`` when safe.

    Every failure mode is non-fatal by design: the worst case is the same
    stale-but-usable worktree the caller would have had before this refresh
    existed. Skipped (with an explanatory log) when:

    * HEAD is detached / not on ``<branch>`` - e.g. a worktree paused
      mid-rebase has a clean working tree but a detached HEAD pointing at the
      pause point; a ``merge --ff-only`` there would silently advance HEAD
      past the pause and break ``git rebase --continue``;
    * ``git fetch origin <branch>`` fails - no ``origin`` remote, an
      unreachable network, or the branch missing upstream; or
    * the branch has diverged from ``origin/<branch>`` (unpushed commits +
      moved origin) - ``--ff-only`` refuses and the unpushed work is
      preserved exactly as it was.
    """
    head = _symbolic_head(run_git=run_git, repo_path=worktree_path, timeout=timeout)
    if head != branch:
        print(
            f"eden: reusing worktree at {worktree_path} (branch {branch!r}) - "
            f"HEAD is not on {branch!r}, skipping origin refresh"
        )
        return
    try:
        run_git(
            ("git", *no_config_lock_flags, "fetch", "origin", branch),
            cwd=worktree_path,
            timeout=timeout,
        )
    except (GitCommandFailed, GitCommandTimeout):
        print(
            f"eden: could not fetch from origin "
            f"(reusing worktree at {worktree_path} as-is, branch {branch!r})"
        )
        return
    before = _rev_parse_head(run_git=run_git, repo_path=worktree_path, timeout=timeout)
    try:
        run_git(
            ("git", *no_config_lock_flags, "merge", "--ff-only", f"origin/{branch}"),
            cwd=worktree_path,
            timeout=timeout,
        )
    except (GitCommandFailed, GitCommandTimeout):
        print(
            f"eden: branch {branch!r} has diverged from origin "
            f"(reusing worktree at {worktree_path} as-is)"
        )
        return
    after = _rev_parse_head(run_git=run_git, repo_path=worktree_path, timeout=timeout)
    if before and after and before != after:
        print(
            f"eden: fast-forwarded worktree at {worktree_path} "
            f"(branch {branch!r}) to origin/{branch}"
        )
