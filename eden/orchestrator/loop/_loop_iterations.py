"""Iteration runner for the orchestrator loop."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path

from eden._types import Timeouts
from eden.abort import AbortSignal
from eden.agents._protocol import Agent
from eden.lifecycle import Hooks
from eden.orchestrator._logging import LoopLogger
from eden.orchestrator._setup import SetupResult
from eden.orchestrator.loop._loop_iteration import run_loop_iteration
from eden.orchestrator.loop._loop_resources import LoopRunResources
from eden.session._protocol import SessionStorage
from eden.streaming import StreamEvent
from eden.worktree._create import WorktreeHandle


def run_loop_iterations(
    *,
    max_iterations: int,
    agent: Agent,
    setup: SetupResult,
    worktree: WorktreeHandle,
    resources: LoopRunResources,
    hooks: Hooks,
    timeouts: Timeouts,
    name: str | None,
    prompt_args: Mapping[str, object] | None,
    resume_session: str | None,
    fork_session: bool,
    flox_env_dir: Path | None,
    idle_timeout: float,
    idle_warning_interval: float | None,
    completion_signal: str | list[str],
    completion_timeout: float | None,
    logger: LoopLogger,
    on_event: Callable[[StreamEvent], None] | None,
    signal: AbortSignal,
    session_storage: SessionStorage | None,
    log_path: Path | None,
) -> None:
    assert resources.handle is not None
    for i in range(max_iterations):
        iteration_result = run_loop_iteration(
            iteration_index=i,
            agent=agent,
            setup=setup,
            worktree=worktree,
            target_branch=resources.target_branch,
            handle=resources.handle,
            hooks=hooks,
            timeouts=timeouts,
            name=name,
            prompt_args=prompt_args,
            resume_session=resume_session,
            fork_session=fork_session,
            flox_env_dir=flox_env_dir,
            idle_timeout=idle_timeout,
            idle_warning_interval=idle_warning_interval,
            completion_signal=completion_signal,
            completion_timeout=completion_timeout,
            logger=logger,
            on_event=on_event,
            signal=signal,
            stdout_chunks=resources.stdout_chunks,
            session_storage=session_storage,
            log_path=log_path,
        )
        resources.rendered_prompt = iteration_result.rendered_prompt
        resources.iterations.append(iteration_result.iteration)
        if iteration_result.completion is not None:
            resources.completion_hit = iteration_result.completion
            break


__all__ = ["run_loop_iterations"]
