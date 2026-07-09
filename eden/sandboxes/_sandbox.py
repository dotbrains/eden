"""Reusable sandbox context-manager wrapper."""

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
from eden.lifecycle import HookPhase, Hooks
from eden.lifecycle._runner import run_host_hooks, run_sandbox_hooks
from eden.logging._config import Logging
from eden.providers._protocols import SandboxHandle, SandboxProvider
from eden.providers._types import ExecResult
from eden.streaming import StreamEvent
from eden.worktree._create import CloseResult, WorktreeHandle

if TYPE_CHECKING:
    from eden.agents._protocol import Agent
    from eden.output import OutputDefinition


def _seconds(value: float | timedelta) -> float:
    if isinstance(value, timedelta):
        return value.total_seconds()
    return float(value)


def _maybe_seconds(value: float | timedelta | None) -> float | None:
    if value is None:
        return None
    return _seconds(value)


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
    """Session id of the most recent ``run()`` that captured one; powers the
    no-argument :meth:`resume` / :meth:`fork` convenience methods."""

    def __enter__(self) -> Sandbox:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> CloseResult:
        """Close the sandbox handle, and the worktree if this sandbox owns it."""
        try:
            run_sandbox_hooks(
                phase=HookPhase.OnClose,
                hooks=self.hooks.sandbox,
                handle=self.handle,
                env=self.create_env,
                timeouts=self.timeouts,
            )
            run_host_hooks(
                phase=HookPhase.OnClose,
                hooks=self.hooks.host,
                worktree_path=self.worktree.worktree_path,
                env=self.create_env,
                timeouts=self.timeouts,
            )
        except BaseException:
            try:
                self.handle.close()
            finally:
                if self.owns_worktree:
                    try:
                        self.worktree.close()
                    except Exception as cleanup_exc:
                        print(f"eden: worktree close also failed: {cleanup_exc}")
            raise
        try:
            self.handle.close()
        except BaseException:
            if self.owns_worktree:
                try:
                    self.worktree.close()
                except Exception as cleanup_exc:
                    print(f"eden: worktree close also failed: {cleanup_exc}")
            raise
        if self.owns_worktree:
            return self.worktree.close()
        return CloseResult(action="released_only", reason="caller-owned-worktree")

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
            timeout=_maybe_seconds(timeout),
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
        from eden.errors import InvalidOptions
        from eden.orchestrator._loop import _run_loop
        from eden.orchestrator._setup import resolve_setup

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
        if resume_session is not None and max_iterations != 1:
            raise InvalidOptions(
                code="config.invalid_options",
                message=(
                    "resume_session= is only valid with max_iterations=1; "
                    f"got max_iterations={max_iterations}"
                ),
            )
        if fork_session and resume_session is None:
            raise InvalidOptions(
                code="config.invalid_options",
                message="fork_session=True requires resume_session=<id>",
                hint=(
                    "fork continues a captured session under a new id; "
                    "pass resume_session=<id> alongside fork_session=True"
                ),
            )
        if output is not None:
            if max_iterations != 1:
                raise InvalidOptions(
                    code="config.invalid_options",
                    message=(
                        "output= is only valid with max_iterations=1; got "
                        f"max_iterations={max_iterations}"
                    ),
                )
            tag_marker = f"<{output.tag}>"
            if tag_marker not in setup.prompt_text:
                raise InvalidOptions(
                    code="config.invalid_options",
                    message=(
                        f"output tag {tag_marker} not referenced in prompt; "
                        "the agent must be told which tag to emit"
                    ),
                )
        abort = signal if signal is not None else AbortController().signal
        result = _run_loop(
            agent=agent,
            sandbox=self.sandbox_provider,
            setup=setup,
            branch_strategy=None,
            max_iterations=max_iterations,
            completion_signal=completion_signal,
            idle_timeout=_seconds(idle_timeout),
            idle_warning_interval=_maybe_seconds(idle_warning_interval),
            completion_timeout=_maybe_seconds(completion_timeout),
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
        from eden.errors import InvalidOptions

        if self._last_session_id is None:
            raise InvalidOptions(
                code="config.invalid_options",
                message=(
                    f"no captured session to {'fork' if fork else 'resume'}; "
                    "call run() first on an agent that captures sessions"
                ),
                hint=(
                    "claude_code captures sessions by default; "
                    "cli_agent needs capture_sessions=True"
                ),
            )
        kwargs: dict[str, object] = dict(overrides)
        kwargs["prompt"] = prompt
        kwargs["resume_session"] = self._last_session_id
        kwargs["fork_session"] = fork
        return self.run(**kwargs)  # type: ignore[arg-type]
