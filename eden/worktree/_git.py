"""Thin wrappers around git commands the worktree manager runs."""

from __future__ import annotations

import os
import subprocess
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from eden.worktree.errors import GitCommandFailed, GitCommandTimeout, WorktreeCollision

# All host-side git invocations bound by this deadline. A wedged local
# git (NFS stall, filesystem repair, runaway hook) would otherwise hang
# Eden indefinitely. 60 s matches upstream's default.
_DEFAULT_GIT_TIMEOUT: float = 60.0

# Prevent ``git worktree add -b`` from writing upstream tracking config into
# ``.git/config`` when user-level branch auto-setup is enabled. That avoids
# needless ``.git/config.lock`` contention during parallel Eden runs.
_NO_CONFIG_LOCK_FLAGS: tuple[str, ...] = (
    "-c",
    "branch.autoSetupMerge=false",
    "-c",
    "push.autoSetupRemote=false",
)
_WORKTREE_MUTEXES: dict[Path, threading.Lock] = {}
_WORKTREE_MUTEXES_GUARD = threading.Lock()


@contextmanager
def _git_worktree_mutex(repo_path: Path) -> Iterator[None]:
    """Serialize Git worktree metadata mutations within this process.

    Git itself writes multiple files under ``.git/worktrees`` during
    ``worktree add/remove``. On macOS Git 2.54, two concurrent adds can observe
    each other's half-written metadata and fail while reading ``commondir``.
    Eden branch locks are intentionally per branch, so add this narrow mutex
    around the Git mutation while preserving concurrency for the agent runs.
    """
    key = repo_path.resolve()
    with _WORKTREE_MUTEXES_GUARD:
        lock = _WORKTREE_MUTEXES.setdefault(key, threading.Lock())
    with lock:
        yield


def c_locale_env() -> dict[str, str]:
    """Inherit ``os.environ`` and pin git's locale to ``C``.

    Eden parses git output via ``--porcelain`` and exit codes today, so
    the immediate motivation is defensive: a future caller that relies
    on human-readable stderr (e.g. "fatal: invalid reference") would
    silently break under non-English locales without this pin.
    Mirrors upstream's ``LC_ALL=C`` fix (v0.6.1, 46eb483) — its
    ``WorktreeManager`` did substring-match localised stderr and broke
    outright in those locales.

    ``LANGUAGE`` is cleared because git prefers it over ``LC_ALL`` for
    message selection.
    """
    return {**os.environ, "LC_ALL": "C", "LANG": "C", "LANGUAGE": ""}


def _run_git(
    argv: tuple[str, ...],
    *,
    cwd: Path,
    timeout: float = _DEFAULT_GIT_TIMEOUT,
) -> tuple[str, str]:
    try:
        proc = subprocess.run(
            argv,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
            env=c_locale_env(),
        )
    except subprocess.TimeoutExpired as exc:
        raise GitCommandTimeout(argv=argv, timeout=timeout) from exc
    if proc.returncode != 0:
        raise GitCommandFailed(argv=argv, exit_code=proc.returncode, stderr=proc.stderr)
    return proc.stdout, proc.stderr


def status_porcelain(*, repo_path: Path, timeout: float = _DEFAULT_GIT_TIMEOUT) -> str:
    stdout, _ = _run_git(("git", "status", "--porcelain"), cwd=repo_path, timeout=timeout)
    return stdout


def branch_exists(*, repo_path: Path, branch: str, timeout: float = _DEFAULT_GIT_TIMEOUT) -> bool:
    try:
        proc = subprocess.run(
            ("git", "rev-parse", "--verify", f"refs/heads/{branch}"),
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
            env=c_locale_env(),
        )
    except subprocess.TimeoutExpired as exc:
        raise GitCommandTimeout(
            argv=("git", "rev-parse", "--verify", f"refs/heads/{branch}"),
            timeout=timeout,
        ) from exc
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


def list_worktrees(
    *, repo_path: Path, timeout: float = _DEFAULT_GIT_TIMEOUT
) -> tuple[_WorktreeRecord, ...]:
    """Return every worktree git knows about for ``repo_path``."""
    stdout, _ = _run_git(("git", "worktree", "list", "--porcelain"), cwd=repo_path, timeout=timeout)
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


def _check_collisions(
    *, repo_path: Path, branch: str, timeout: float = _DEFAULT_GIT_TIMEOUT
) -> None:
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
    for record in list_worktrees(repo_path=repo_path, timeout=timeout):
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
    timeout: float = _DEFAULT_GIT_TIMEOUT,
) -> None:
    with _git_worktree_mutex(repo_path):
        _check_collisions(repo_path=repo_path, branch=branch, timeout=timeout)
        _run_git(
            (
                "git",
                *_NO_CONFIG_LOCK_FLAGS,
                "worktree",
                "add",
                "-b",
                branch,
                str(worktree_path),
                base,
            ),
            cwd=repo_path,
            timeout=timeout,
        )


def worktree_remove(
    *, repo_path: Path, worktree_path: Path, timeout: float = _DEFAULT_GIT_TIMEOUT
) -> None:
    with _git_worktree_mutex(repo_path):
        _run_git(
            ("git", "worktree", "remove", "--force", str(worktree_path)),
            cwd=repo_path,
            timeout=timeout,
        )


def _symbolic_head(*, repo_path: Path, timeout: float = _DEFAULT_GIT_TIMEOUT) -> str | None:
    """Return the branch HEAD points at, or ``None`` when detached.

    ``git symbolic-ref --quiet HEAD`` exits non-zero on a detached HEAD; we
    map both that and any timeout to ``None`` so callers treat them the same
    as "not on a branch".
    """
    try:
        proc = subprocess.run(
            ("git", "symbolic-ref", "--quiet", "HEAD"),
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
            env=c_locale_env(),
        )
    except subprocess.TimeoutExpired:
        return None
    if proc.returncode != 0:
        return None
    ref = proc.stdout.strip()
    prefix = "refs/heads/"
    return ref[len(prefix) :] if ref.startswith(prefix) else None


def _rev_parse_head(*, repo_path: Path, timeout: float = _DEFAULT_GIT_TIMEOUT) -> str:
    try:
        stdout, _ = _run_git(("git", "rev-parse", "HEAD"), cwd=repo_path, timeout=timeout)
    except (GitCommandFailed, GitCommandTimeout):
        return ""
    return stdout.strip()


def head_sha(*, repo_path: Path, timeout: float = _DEFAULT_GIT_TIMEOUT) -> str:
    """Return ``repo_path``'s current HEAD SHA, or ``""`` if it can't be read.

    The run loop snapshots this immediately after carving the worktree and
    before the agent runs, so the SHA marks the commit census baseline. An
    unborn branch, detached/garbage HEAD, or timed-out git maps to ``""`` —
    :func:`new_commits` treats that as "no baseline" and reports no commits
    rather than raising.
    """
    return _rev_parse_head(repo_path=repo_path, timeout=timeout)


def new_commits(
    *, worktree_path: Path, base_sha: str, timeout: float = _DEFAULT_GIT_TIMEOUT
) -> tuple[str, ...]:
    """Return SHAs committed on the worktree's branch since ``base_sha``.

    Runs ``git rev-list <base_sha>..HEAD`` in ``worktree_path`` to list the
    commits the agent created during this run, newest first. The run loop
    bounds it with ``Timeouts.commit_collection``.

    Best-effort by design: an empty ``base_sha`` (HEAD was unreadable at run
    start), an invalid ref, or a timed-out git all return ``()`` rather than
    raising — a failed commit census must never sink an otherwise-good run.
    Bind-mount providers (no-sandbox/docker/podman) preserve the agent's
    commits on the branch, so this yields real SHAs; isolated/cloud providers
    patch-sync file changes only, leaving the host worktree with no new
    commits, so an empty result there is correct, not a failure.
    """
    if not base_sha:
        return ()
    try:
        stdout, _ = _run_git(
            ("git", "rev-list", f"{base_sha}..HEAD"),
            cwd=worktree_path,
            timeout=timeout,
        )
    except (GitCommandFailed, GitCommandTimeout):
        return ()
    return tuple(line.strip() for line in stdout.splitlines() if line.strip())


def refresh_from_origin(
    *, worktree_path: Path, branch: str, timeout: float = _DEFAULT_GIT_TIMEOUT
) -> None:
    """Fast-forward a reused, clean worktree to ``origin/<branch>`` when safe.

    Mirrors upstream's ``fastForwardFromOrigin`` (v0.7.0). Every failure
    mode is non-fatal by design: the worst case is the same stale-but-usable
    worktree the caller would have had before this refresh existed. Skipped
    (with an explanatory log) when:

    * HEAD is detached / not on ``<branch>`` — e.g. a worktree paused
      mid-rebase has a clean working tree but a detached HEAD pointing at the
      pause point; a ``merge --ff-only`` there would silently advance HEAD
      past the pause and break ``git rebase --continue``;
    * ``git fetch origin <branch>`` fails — no ``origin`` remote, an
      unreachable network, or the branch missing upstream; or
    * the branch has diverged from ``origin/<branch>`` (unpushed commits +
      moved origin) — ``--ff-only`` refuses and the unpushed work is
      preserved exactly as it was.
    """
    head = _symbolic_head(repo_path=worktree_path, timeout=timeout)
    if head != branch:
        print(
            f"eden: reusing worktree at {worktree_path} (branch {branch!r}) — "
            f"HEAD is not on {branch!r}, skipping origin refresh"
        )
        return
    try:
        _run_git(
            ("git", *_NO_CONFIG_LOCK_FLAGS, "fetch", "origin", branch),
            cwd=worktree_path,
            timeout=timeout,
        )
    except (GitCommandFailed, GitCommandTimeout):
        print(
            f"eden: could not fetch from origin "
            f"(reusing worktree at {worktree_path} as-is, branch {branch!r})"
        )
        return
    before = _rev_parse_head(repo_path=worktree_path, timeout=timeout)
    try:
        _run_git(
            ("git", *_NO_CONFIG_LOCK_FLAGS, "merge", "--ff-only", f"origin/{branch}"),
            cwd=worktree_path,
            timeout=timeout,
        )
    except (GitCommandFailed, GitCommandTimeout):
        print(
            f"eden: branch {branch!r} has diverged from origin "
            f"(reusing worktree at {worktree_path} as-is)"
        )
        return
    after = _rev_parse_head(repo_path=worktree_path, timeout=timeout)
    if before and after and before != after:
        print(
            f"eden: fast-forwarded worktree at {worktree_path} "
            f"(branch {branch!r}) to origin/{branch}"
        )
