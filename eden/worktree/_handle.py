"""Worktree handle types and lifecycle helpers."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol

from eden.worktree._git import _DEFAULT_GIT_TIMEOUT, status_porcelain
from eden.worktree._lock import _LockHandle
from eden.worktree._worktree_ops import worktree_remove

if TYPE_CHECKING:
    from eden._types import RunResult, Timeouts
    from eden.abort import AbortSignal
    from eden.agents._protocol import Agent
    from eden.lifecycle import Hooks
    from eden.logging import Logging
    from eden.orchestrator.interactive import InteractiveResult
    from eden.output import OutputDefinition
    from eden.providers._protocols import SandboxProvider
    from eden.providers._types import Mount
    from eden.sandboxes._sandbox import Sandbox
    from eden.streaming import StreamEvent


class _StatusPorcelain(Protocol):
    def __call__(self, *, repo_path: Path, timeout: float = _DEFAULT_GIT_TIMEOUT) -> str: ...


class _WorktreeRemove(Protocol):
    def __call__(
        self,
        *,
        repo_path: Path,
        worktree_path: Path,
        timeout: float = _DEFAULT_GIT_TIMEOUT,
    ) -> None: ...


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
    _status_porcelain: _StatusPorcelain = field(default=status_porcelain, repr=False)
    _worktree_remove: _WorktreeRemove = field(default=worktree_remove, repr=False)

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
        from eden.orchestrator.interactive import interactive

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
                self._status_porcelain(
                    repo_path=self.worktree_path,
                    timeout=self._git_timeout,
                ).strip()
            )
            if dirty:
                print(f"eden: leaving dirty worktree on disk at {self.worktree_path}")
                return CloseResult(action="preserved", reason="dirty")
            self._worktree_remove(
                repo_path=self.host_repo_path,
                worktree_path=self.worktree_path,
                timeout=self._git_timeout,
            )
            return CloseResult(action="removed")
        finally:
            self._lock_handle.release()
