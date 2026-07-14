from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path

from eden._types import Iteration, Timeouts
from eden.abort import AbortSignal
from eden.agents._flox import flox_wrap
from eden.agents._protocol import Agent
from eden.lifecycle import Hooks
from eden.orchestrator._agent_exec import execute_agent_iteration
from eden.orchestrator._agent_failure import raise_if_agent_failed_without_completion
from eden.orchestrator._logging import LoopLogger
from eden.orchestrator._session_capture import capture_iteration_session
from eden.orchestrator._setup import SetupResult
from eden.orchestrator.loop._agent_stream import build_agent_command
from eden.orchestrator.loop._iteration_events import emit_context_window
from eden.orchestrator.loop._iteration_hooks import (
    run_iteration_end_hooks,
    run_iteration_start_hooks,
)
from eden.orchestrator.loop._iteration_prompt import render_iteration_prompt
from eden.orchestrator.loop._loop_result import LoopIterationResult
from eden.providers._protocols import SandboxHandle
from eden.session._protocol import SessionStorage
from eden.streaming import StreamEvent
from eden.streaming._bounded_tail import BoundedTail
from eden.worktree._create import WorktreeHandle

_SIDECHAIN_MTIME_SLACK = 2.0


def _utcnow() -> datetime:
    return datetime.now(UTC)


def run_loop_iteration(
    *,
    iteration_index: int,
    agent: Agent,
    setup: SetupResult,
    worktree: WorktreeHandle,
    target_branch: str,
    handle: SandboxHandle,
    hooks: Hooks,
    timeouts: Timeouts,
    name: str | None,
    prompt_args: Mapping[str, str] | None,
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
    stdout_chunks: BoundedTail,
    session_storage: SessionStorage | None,
    log_path: Path | None,
) -> LoopIterationResult:
    signal.raise_if_aborted()
    run_iteration_start_hooks(
        hooks=hooks,
        handle=handle,
        worktree=worktree,
        env=setup.merged_env,
        timeouts=timeouts,
    )

    rendered_prompt = render_iteration_prompt(
        setup=setup,
        prompt_args=prompt_args,
        source_branch=worktree.branch,
        target_branch=target_branch,
        handle=handle,
    )
    argv = build_agent_command(
        agent=agent,
        iteration=iteration_index,
        rendered_prompt=rendered_prompt,
        handle=handle,
        worktree_path=worktree.worktree_path,
        branch=worktree.branch,
        name=name,
        resume_session=resume_session,
        fork_session=fork_session,
    )
    argv = flox_wrap(argv, flox_env=flox_env_dir)

    iter_started_at = time.time() - _SIDECHAIN_MTIME_SLACK

    agent_execution = execute_agent_iteration(
        agent=agent,
        argv=argv,
        env=setup.merged_env,
        handle=handle,
        worktree_path=worktree.worktree_path,
        branch=worktree.branch,
        name=name,
        resume_session=resume_session,
        rendered_prompt=rendered_prompt,
        iteration=iteration_index,
        idle_timeout=idle_timeout,
        idle_warning_interval=idle_warning_interval,
        completion_signal=completion_signal,
        completion_timeout=completion_timeout,
        logger=logger,
        on_event=on_event,
        signal=signal,
        stdout_chunks=stdout_chunks,
        timestamp=_utcnow,
    )

    raise_if_agent_failed_without_completion(
        agent_name=agent.name,
        iteration=iteration_index,
        execution=agent_execution,
        stdout=stdout_chunks.to_string(),
        branch=worktree.branch,
        worktree_path=worktree.worktree_path,
        log_path=log_path,
        sink=logger.sink,
        on_event=on_event,
        timestamp=_utcnow,
    )

    iter_session_file = capture_iteration_session(
        session_storage=session_storage,
        handle=handle,
        session_id=agent_execution.session_id,
        host_repo_path=setup.cwd,
        target_branch=target_branch,
        iteration=iteration_index,
        since=iter_started_at,
        agent_name=agent.name,
        timestamp=_utcnow(),
        sink=logger.sink,
    )

    emit_context_window(
        agent_name=agent.name,
        iteration=iteration_index,
        usage=agent_execution.usage,
        logger=logger,
        on_event=on_event,
    )

    run_iteration_end_hooks(
        hooks=hooks,
        handle=handle,
        worktree=worktree,
        env=setup.merged_env,
        timeouts=timeouts,
    )

    return LoopIterationResult(
        iteration=Iteration(
            index=iteration_index,
            completion_signal=agent_execution.completion,
            session_id=agent_execution.session_id,
            session_file_path=iter_session_file,
            usage=agent_execution.usage,
        ),
        completion=agent_execution.completion,
        rendered_prompt=rendered_prompt,
    )


__all__ = ["LoopIterationResult", "run_loop_iteration"]
