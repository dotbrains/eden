"""Worktree manager: create_worktree, WorktreeHandle, CloseResult."""

from __future__ import annotations

import datetime as _dt
import re
import secrets
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from eden.providers._types import BranchStrategy
from eden.worktree._git import (
    _DEFAULT_GIT_TIMEOUT,
    branch_exists,
    list_worktrees,
    refresh_from_origin,
    status_porcelain,
    worktree_add,
    worktree_remove,
)
from eden.worktree._lock import _LockHandle, acquire_lock
from eden.worktree.errors import BranchExists, DirtyHostBlocked

if TYPE_CHECKING:
    from eden._types import RunResult, Timeouts
    from eden.abort import AbortSignal
    from eden.agents._protocol import Agent
    from eden.lifecycle import Hooks
    from eden.logging import Logging
    from eden.orchestrator._interactive import InteractiveResult
    from eden.output import OutputDefinition
    from eden.providers._protocols import SandboxProvider
    from eden.providers._types import Mount
    from eden.sandboxes._sandbox import Sandbox
    from eden.streaming import StreamEvent

_SANITIZE_RE = re.compile(r"[^a-z0-9._-]+")


def _sanitize(name: str) -> str:
    s = _SANITIZE_RE.sub("-", name.lower()).strip("-")
    return s or "x"


@dataclass(frozen=True)
class CloseResult:
    action: Literal["removed", "preserved", "released_only"]
    reason: str | None = None


@dataclass(frozen=True)
class WorktreeHandle:
    branch: str
    worktree_path: Path
    host_repo_path: Path
    managed: bool
    _lock_handle: _LockHandle = field(repr=False)
    _closed: list[bool] = field(default_factory=lambda: [False], repr=False)
    _git_timeout: float = field(default=_DEFAULT_GIT_TIMEOUT, repr=False)

    def __enter__(self) -> WorktreeHandle:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def create_sandbox(
        self,
        *,
        sandbox: SandboxProvider,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        mounts: tuple[Mount, ...] | None = None,
        name: str | None = None,
        hooks: Hooks | None = None,
        copy_to_worktree: list[str] | None = None,
        timeouts: Timeouts | None = None,
    ) -> Sandbox:
        """Create a sandbox backed by this worktree.

        The returned sandbox does not own the worktree: closing it tears down
        only the provider handle. Call :meth:`close` on this worktree when the
        whole workflow is finished.
        """
        from eden.sandboxes import create_sandbox

        return create_sandbox(
            sandbox=sandbox,
            worktree=self,
            cwd=cwd,
            env=env,
            mounts=mounts,
            name=name,
            hooks=hooks,
            copy_to_worktree=copy_to_worktree,
            timeouts=timeouts,
        )

    def run(
        self,
        *,
        agent: Agent,
        sandbox: SandboxProvider,
        prompt: str | None = None,
        prompt_file: str | Path | None = None,
        prompt_args: Mapping[str, str] | None = None,
        env: Mapping[str, str] | None = None,
        mounts: tuple[Mount, ...] | None = None,
        max_iterations: int = 1,
        completion_signal: str | list[str] = "<promise>COMPLETE</promise>",
        idle_timeout: float | timedelta = 600.0,
        idle_warning_interval: float | timedelta | None = None,
        completion_timeout: float | timedelta | None = 60.0,
        name: str | None = None,
        hooks: Hooks | None = None,
        timeouts: Timeouts | None = None,
        on_event: Callable[[StreamEvent], None] | None = None,
        logging: Logging | None = None,
        signal: AbortSignal | None = None,
        output: OutputDefinition | None = None,
        resume_session: str | None = None,
        fork_session: bool = False,
        copy_to_worktree: list[str] | None = None,
    ) -> RunResult:
        """Run an agent in a short-lived sandbox backed by this worktree."""
        with self.create_sandbox(
            sandbox=sandbox,
            env=env,
            mounts=mounts,
            name=name,
            hooks=hooks,
            copy_to_worktree=copy_to_worktree,
            timeouts=timeouts,
        ) as sb:
            return sb.run(
                agent=agent,
                prompt=prompt,
                prompt_file=prompt_file,
                prompt_args=prompt_args,
                env=env,
                max_iterations=max_iterations,
                completion_signal=completion_signal,
                idle_timeout=idle_timeout,
                idle_warning_interval=idle_warning_interval,
                completion_timeout=completion_timeout,
                name=name,
                hooks=hooks,
                timeouts=timeouts,
                on_event=on_event,
                logging=logging,
                signal=signal,
                output=output,
                resume_session=resume_session,
                fork_session=fork_session,
            )

    def interactive(
        self,
        *,
        agent: Agent,
        sandbox: SandboxProvider | None = None,
        prompt: str | None = None,
        prompt_file: str | Path | None = None,
        prompt_args: Mapping[str, str] | None = None,
        env: Mapping[str, str] | None = None,
        name: str | None = None,
        hooks: Hooks | None = None,
        collect_args: bool | None = None,
        signal: AbortSignal | None = None,
        timeouts: Timeouts | None = None,
    ) -> InteractiveResult:
        """Run an interactive agent session in this worktree."""
        from eden.orchestrator._interactive import interactive

        return interactive(
            agent=agent,
            sandbox=sandbox,
            prompt=prompt,
            prompt_file=prompt_file,
            prompt_args=prompt_args,
            env=env,
            name=name,
            hooks=hooks,
            collect_args=collect_args,
            signal=signal,
            timeouts=timeouts,
            _existing_worktree=self,
        )

    def close(self) -> CloseResult:
        if self._closed[0]:
            return CloseResult(action="released_only", reason="already-closed")
        self._closed[0] = True
        try:
            if not self.managed:
                return CloseResult(action="released_only")
            dirty = bool(
                status_porcelain(repo_path=self.worktree_path, timeout=self._git_timeout).strip()
            )
            if dirty:
                print(f"eden: leaving dirty worktree on disk at {self.worktree_path}")
                return CloseResult(action="preserved", reason="dirty")
            worktree_remove(
                repo_path=self.host_repo_path,
                worktree_path=self.worktree_path,
                timeout=self._git_timeout,
            )
            return CloseResult(action="removed")
        finally:
            self._lock_handle.release()


def _generate_branch(name_hint: str | None) -> str:
    suffix = secrets.token_hex(4)
    if name_hint:
        return f"eden/{_sanitize(name_hint)}-{suffix}"
    ts = _dt.datetime.now().strftime("%Y%m%d%H%M%S")
    return f"eden/{ts}-{suffix}"


def _eden_dir(host_repo_path: Path) -> Path:
    """Return the resolved (symlink-free) path to ``<repo>/.eden/``.

    Git keys its worktree records by realpath. When users symlink
    ``.eden/`` to another disk (a common setup when the host repo lives
    on a small SSD), passing the symlink-relative path to
    ``git worktree add / remove`` makes git's internal lookup miss its
    own records. Resolving once at the entry point fixes both branches.

    The directory is created if it does not exist so ``.resolve()``
    returns an absolute path on every platform (Windows in particular
    requires the target to exist for full resolution).
    """
    eden_dir = host_repo_path / ".eden"
    eden_dir.mkdir(exist_ok=True)
    return eden_dir.resolve()


def _lock_path_for(host_repo_path: Path, branch: str | None) -> Path:
    base = _eden_dir(host_repo_path) / "worktrees"
    if branch is None:
        return base / "_head.lock"
    return base / f"{_sanitize(branch)}.lock"


def _worktree_path_for(host_repo_path: Path, branch: str) -> Path:
    return _eden_dir(host_repo_path) / "worktrees" / _sanitize(branch)


def _ensure_eden_gitignore(host_repo_path: Path) -> None:
    """Write .eden/.gitignore so git ignores eden's own metadata directory."""
    eden_dir = _eden_dir(host_repo_path)
    gitignore = eden_dir / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("*\n", encoding="utf-8")


def create_worktree(
    *,
    host_repo_path: Path,
    strategy: BranchStrategy,
    name_hint: str | None = None,
    throw_on_duplicate_worktree: bool = True,
    git_timeout: float = _DEFAULT_GIT_TIMEOUT,
) -> WorktreeHandle:
    """Carve (or reuse) a worktree per ``strategy``.

    ``throw_on_duplicate_worktree`` only applies to the ``named`` strategy.
    When ``False`` and the named branch already exists with a worktree on
    disk, the existing worktree is reused (returned with ``managed=False``
    so it is not removed on close). When ``True`` (default), a duplicate
    raises :class:`BranchExists`. Other strategies are unaffected:
    ``head`` uses the host repo directly and ``merge_to_head`` always
    generates a fresh branch name.

    ``git_timeout`` is the per-command deadline for every host-side git
    invocation this carve runs; it is also stored on the returned handle so
    ``close()`` reuses it for the teardown ``git worktree remove``. Callers
    in the run loop pass ``Timeouts.git_setup``.
    """
    # Ensure .eden/ is gitignored regardless of strategy so metadata files
    # created by any path don't surface as untracked in the host repo.
    _ensure_eden_gitignore(host_repo_path)

    if strategy.tag == "head":
        dirty = status_porcelain(repo_path=host_repo_path, timeout=git_timeout).strip()
        if dirty:
            files = tuple(line[3:] for line in dirty.splitlines() if len(line) > 3)[:10]
            raise DirtyHostBlocked(host_repo_path=host_repo_path, dirty_files=files)
        lock = acquire_lock(_lock_path_for(host_repo_path, None))
        return WorktreeHandle(
            branch="HEAD",
            worktree_path=host_repo_path,
            host_repo_path=host_repo_path,
            managed=False,
            _lock_handle=lock,
            _git_timeout=git_timeout,
        )

    if strategy.tag == "merge_to_head":
        branch = _generate_branch(name_hint)
    else:  # named
        assert strategy.branch is not None
        branch = strategy.branch
        if branch_exists(repo_path=host_repo_path, branch=branch, timeout=git_timeout):
            if throw_on_duplicate_worktree:
                raise BranchExists(branch=branch)
            # Reuse path: find the existing worktree for this branch.
            for record in list_worktrees(repo_path=host_repo_path, timeout=git_timeout):
                if record.branch == branch:
                    lock = acquire_lock(_lock_path_for(host_repo_path, branch))
                    # Refresh a clean reused worktree from origin so the agent
                    # never runs against stale code; a dirty tree is reused
                    # untouched. All refresh failures fall back to plain reuse.
                    has_changes = bool(
                        status_porcelain(repo_path=record.path, timeout=git_timeout).strip()
                    )
                    if has_changes:
                        print(
                            f"eden: reusing worktree at {record.path} "
                            f"(branch {branch!r}) — worktree has uncommitted changes"
                        )
                    else:
                        refresh_from_origin(
                            worktree_path=record.path, branch=branch, timeout=git_timeout
                        )
                    return WorktreeHandle(
                        branch=branch,
                        worktree_path=record.path,
                        host_repo_path=host_repo_path,
                        managed=False,
                        _lock_handle=lock,
                        _git_timeout=git_timeout,
                    )
            # Branch exists but isn't checked out by any worktree — we have
            # no on-disk worktree to reuse. Fall through to BranchExists so
            # the caller knows their state is unexpected.
            raise BranchExists(branch=branch)

    wt_path = _worktree_path_for(host_repo_path, branch)
    lock = acquire_lock(_lock_path_for(host_repo_path, branch))
    try:
        worktree_add(
            repo_path=host_repo_path,
            worktree_path=wt_path,
            branch=branch,
            base=strategy.base,
            timeout=git_timeout,
        )
    except Exception:
        lock.release()
        raise

    return WorktreeHandle(
        branch=branch,
        worktree_path=wt_path,
        host_repo_path=host_repo_path,
        managed=True,
        _lock_handle=lock,
        _git_timeout=git_timeout,
    )
