from __future__ import annotations

import shlex
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from eden._types import RunResult, Timeouts
from eden.abort import AbortSignal
from eden.abort._signal import AbortController
from eden.lifecycle import Hooks
from eden.logging._config import Logging
from eden.providers._protocols import SandboxHandle, SandboxProvider
from eden.providers._types import ExecResult
from eden.sandboxes._duration import maybe_seconds, seconds
from eden.sandboxes._sandbox_continue import continue_sandbox_session
from eden.sandboxes._sandbox_lifecycle import close_sandbox
from eden.sandboxes._sandbox_run import validate_sandbox_run_options
from eden.streaming import StreamEvent
from eden.worktree._create import CloseResult, WorktreeHandle

if TYPE_CHECKING:
    from eden.agents._protocol import Agent
    from eden.output import OutputDefinition


@dataclass
class Sandbox:
    worktree: WorktreeHandle
    handle: SandboxHandle
    sandbox_provider: SandboxProvider
    cwd: Path | None = None
    owns_worktree: bool = True
    hooks: Hooks = field(default_factory=Hooks)
    create_env: Mapping[str, str] = field(default_factory=dict)
    timeouts: Timeouts = field(default_factory=Timeouts)
    _last_session_id: str | None = field(default=None, repr=False, compare=False)
    """Most recent captured session id for no-argument ``resume`` / ``fork``."""

    def __enter__(self) -> Sandbox:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> CloseResult:
        return close_sandbox(
            worktree=self.worktree,
            handle=self.handle,
            owns_worktree=self.owns_worktree,
            hooks=self.hooks,
            create_env=self.create_env,
            timeouts=self.timeouts,
        )

    def exec(
        self,
        cmd: str,
        *,
        on_line: Callable[[str], None] | None = None,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | timedelta | None = None,
        stdin: str | None = None,
        sudo: bool = False,
    ) -> ExecResult:
        """Run ``cmd`` inside this reusable sandbox."""
        exec_cmd = f"sudo -E -- sh -c {shlex.quote(cmd)}" if sudo else cmd
        return self.handle.exec(
            exec_cmd,
            on_line=on_line,
            cwd=cwd if cwd is not None else self.cwd or self.worktree.worktree_path,
            env=env,
            timeout=maybe_seconds(timeout),
            stdin=stdin,
        )

    def run(
        self,
        *,
        agent: Agent,
        prompt: str | None = None,
        prompt_file: str | Path | None = None,
        prompt_args: Mapping[str, str] | None = None,
        env: Mapping[str, str] | None = None,
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
    ) -> RunResult:
        """Run an agent against this existing sandbox + worktree."""
        from eden.orchestrator._setup import resolve_setup
        from eden.orchestrator.loop import _run_loop

        cwd_path = self.cwd if self.cwd is not None else self.worktree.host_repo_path
        provider_env: dict[str, str] = {}
        setup = resolve_setup(
            prompt=prompt,
            prompt_file=prompt_file,
            prompt_args=prompt_args,
            cwd=cwd_path,
            env=env,
            provider_env=provider_env,
            sandbox_kind=self.sandbox_provider.kind,
        )
        validate_sandbox_run_options(
            resume_session=resume_session,
            fork_session=fork_session,
            max_iterations=max_iterations,
            output_tag=output.tag if output is not None else None,
            prompt_text=setup.prompt_text,
        )
        abort = signal if signal is not None else AbortController().signal
        result = _run_loop(
            agent=agent,
            sandbox=self.sandbox_provider,
            setup=setup,
            branch_strategy=None,
            max_iterations=max_iterations,
            completion_signal=completion_signal,
            idle_timeout=seconds(idle_timeout),
            idle_warning_interval=maybe_seconds(idle_warning_interval),
            completion_timeout=maybe_seconds(completion_timeout),
            name=name,
            hooks=hooks if hooks is not None else Hooks(),
            timeouts=timeouts if timeouts is not None else Timeouts(),
            on_event=on_event,
            logging_cfg=logging,
            signal=abort,
            prompt_args=prompt_args,
            output=output,
            resume_session=resume_session,
            fork_session=fork_session,
            existing_worktree=self.worktree,
            existing_handle=self.handle,
        )
        if result.session_id is not None and not fork_session:
            self._last_session_id = result.session_id
        return result

    def resume(self, prompt: str, **overrides: object) -> RunResult:
        """Continue this sandbox's most recent session with a follow-up prompt."""
        return self._continue(prompt, fork=False, overrides=overrides)

    def fork(self, prompt: str, **overrides: object) -> RunResult:
        """Branch this sandbox's most recent session into a new one."""
        return self._continue(prompt, fork=True, overrides=overrides)

    def _continue(self, prompt: str, *, fork: bool, overrides: Mapping[str, object]) -> RunResult:
        return continue_sandbox_session(
            run=self.run,
            last_session_id=self._last_session_id,
            prompt=prompt,
            fork=fork,
            overrides=overrides,
        )
