"""Public orchestrator surface: run() + create_worktree()."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import timedelta
from pathlib import Path

from eden._types import RunResult, Timeouts
from eden.abort import AbortSignal
from eden.abort._signal import AbortController
from eden.agents._env import agent_env
from eden.agents._protocol import Agent
from eden.lifecycle import Hooks
from eden.logging._config import Logging
from eden.orchestrator._setup import SetupResult, resolve_setup
from eden.orchestrator._worktree_api import create_worktree
from eden.orchestrator.loop import _run_loop
from eden.orchestrator.run._run_output_retry import (
    corrective_output_prompt as _corrective_output_prompt,
)
from eden.orchestrator.run._run_output_retry import (
    run_with_output_retries,
)
from eden.orchestrator.run._run_preflight import (
    maybe_seconds,
    precheck_resume_session,
    seconds,
    validate_copy_to_worktree,
    validate_output_options,
    validate_session_options,
)
from eden.output import OutputDefinition
from eden.providers._protocols import SandboxProvider
from eden.providers._types import BranchStrategy
from eden.streaming import StreamEvent


def run(
    *,
    agent: Agent,
    sandbox: SandboxProvider,
    prompt: str | None = None,
    prompt_file: str | Path | None = None,
    prompt_args: Mapping[str, str] | None = None,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    branch_strategy: BranchStrategy | None = None,
    base_branch: str | None = None,
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
    throw_on_duplicate_worktree: bool = True,
) -> RunResult:
    """Run an agent against a sandbox in a managed worktree, returning RunResult."""
    if signal is not None:
        signal.raise_if_aborted()

    cwd_path = Path(cwd) if cwd is not None else None
    setup = resolve_setup(
        prompt=prompt,
        prompt_file=prompt_file,
        prompt_args=prompt_args,
        cwd=cwd_path,
        env=env,
        provider_env=agent_env(agent),
        sandbox_kind=sandbox.kind,
    )
    validate_session_options(
        agent=agent,
        sandbox=sandbox,
        resume_session=resume_session,
        fork_session=fork_session,
        max_iterations=max_iterations,
        host_repo_path=setup.cwd,
    )
    validate_output_options(
        output=output,
        max_iterations=max_iterations,
        prompt_text=setup.prompt_text,
    )
    validate_copy_to_worktree(
        copy_to_worktree=copy_to_worktree,
        branch_strategy=branch_strategy,
        sandbox_kind=sandbox.kind,
        base_branch=base_branch,
    )
    abort = signal if signal is not None else AbortController().signal

    def _invoke(setup_: SetupResult, resume_: str | None, fork_: bool) -> RunResult:
        return _run_loop(
            agent=agent,
            sandbox=sandbox,
            setup=setup_,
            branch_strategy=branch_strategy,
            base_branch=base_branch,
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
            resume_session=resume_,
            fork_session=fork_,
            copy_to_worktree=copy_to_worktree,
            throw_on_duplicate_worktree=throw_on_duplicate_worktree,
        )

    max_retries = output.max_retries if output is not None else 0
    if max_retries <= 0:
        return _invoke(setup, resume_session, fork_session)

    assert output is not None  # max_retries > 0 implies output was configured
    return run_with_output_retries(
        output=output,
        setup=setup,
        resume_session=resume_session,
        fork_session=fork_session,
        max_retries=max_retries,
        invoke=_invoke,
        precheck_resume=lambda session_id: precheck_resume_session(
            agent=agent,
            sandbox=sandbox,
            resume_session=session_id,
            host_repo_path=setup.cwd,
        ),
        prompt_args=prompt_args,
        cwd_path=cwd_path,
        env=env,
        sandbox=sandbox,
    )


__all__ = ["_corrective_output_prompt", "create_worktree", "run"]
