"""Worktree-specific exceptions."""

from __future__ import annotations

from pathlib import Path

from eden.errors import EdenError


class WorktreeError(EdenError):
    """Base for worktree errors."""


class WorktreeLocked(WorktreeError):
    def __init__(self, *, lock_path: Path, holder_pid: int) -> None:
        self.lock_path = lock_path
        self.holder_pid = holder_pid
        super().__init__(f"worktree lock at {lock_path} held by pid {holder_pid}")


class DirtyHostBlocked(WorktreeError):
    def __init__(self, *, host_repo_path: Path, dirty_files: tuple[str, ...]) -> None:
        self.host_repo_path = host_repo_path
        self.dirty_files = dirty_files
        joined = ", ".join(dirty_files[:10]) or "(unknown)"
        super().__init__(f"host repo {host_repo_path} has uncommitted changes: {joined}")


class BranchExists(WorktreeError):
    def __init__(
        self,
        *,
        branch: str,
        conflict_path: Path | None = None,
        hint: str | None = None,
    ) -> None:
        self.branch = branch
        self.conflict_path = conflict_path
        self.hint = hint
        msg = f"branch {branch!r} already exists"
        if conflict_path is not None:
            msg = f"{msg} and is checked out at {conflict_path}"
        if hint:
            msg = f"{msg}\nhint: {hint}"
        super().__init__(msg)


class WorktreeCollision(WorktreeError):
    """``git worktree add`` would collide with an existing checkout.

    Raised in two distinct shapes:

    * ``reason == "branch_in_use"`` — the target branch is already checked
      out by a different worktree (git refuses to check the same branch
      out twice). ``conflict_path`` holds the path of that worktree.
    * ``reason == "rebase_in_progress"`` — the host repo is mid-rebase,
      mid-merge, or mid-cherry-pick. Spawning a new worktree at this
      point produces cryptic git errors. ``conflict_path`` holds the
      ``.git/<state>`` path that signalled the in-flight operation.

    Carries a recovery hint pointing at the underlying conflict so the
    user can untangle it without parsing git stderr.
    """

    def __init__(
        self,
        *,
        branch: str,
        reason: str,
        conflict_path: Path | None = None,
        hint: str | None = None,
    ) -> None:
        self.branch = branch
        self.reason = reason
        self.conflict_path = conflict_path
        self.hint = hint
        suffix = f" (conflict at {conflict_path})" if conflict_path is not None else ""
        msg = f"cannot carve worktree for branch {branch!r}: {reason}{suffix}"
        if hint:
            msg = f"{msg}\nhint: {hint}"
        super().__init__(msg)


class GitCommandFailed(WorktreeError):
    def __init__(self, *, argv: tuple[str, ...], exit_code: int, stderr: str) -> None:
        self.argv = argv
        self.exit_code = exit_code
        self.stderr = stderr
        super().__init__(f"git command failed (exit {exit_code}): {' '.join(argv)}\n{stderr}")


class GitCommandTimeout(WorktreeError):
    """A host-side git subprocess exceeded its deadline.

    Raised when the local ``git`` invocation exceeds the per-call timeout
    (default 60 s). Covers wedged local-filesystem hangs (NFS stalls,
    filesystem repair, runaway git hooks); does NOT cover git operations
    the agent runs inside the sandbox (those bound by ``Timeouts.iteration_step``).
    """

    def __init__(self, *, argv: tuple[str, ...], timeout: float) -> None:
        self.argv = argv
        self.timeout = timeout
        super().__init__(
            f"git command timed out after {timeout:.1f}s: {' '.join(argv)}\n"
            f"hint: a wedged host-side git may indicate a filesystem stall or runaway hook"
        )
