from __future__ import annotations

from collections.abc import Callable, Mapping

from eden._types import RunResult, Timeouts
from eden.abort import AbortSignal
from eden.agents._protocol import Agent
from eden.lifecycle import Hooks
from eden.logging._config import Logging
from eden.orchestrator._setup import SetupResult
from eden.orchestrator.loop._loop_cleanup import close_loop_resources
from eden.orchestrator.loop._loop_finalize import finalize_loop_sandbox
from eden.orchestrator.loop._loop_iterations import run_loop_iterations
from eden.orchestrator.loop._loop_resources import prepare_loop_run_resources, prepare_loop_worktree
from eden.orchestrator.loop._loop_result import build_loop_result
from eden.orchestrator.loop._loop_session import prepare_loop_session_context
from eden.orchestrator.loop._loop_startup import start_loop_runtime
from eden.output import OutputDefinition
from eden.providers._protocols import SandboxHandle, SandboxProvider
from eden.providers._types import BranchStrategy
from eden.streaming import StreamEvent
from eden.worktree._create import WorktreeHandle


def _run_loop(
    *,
    agent: Agent,
    sandbox: SandboxProvider,
    setup: SetupResult,
    branch_strategy: BranchStrategy | None,
    base_branch: str | None = None,
    max_iterations: int,
    completion_signal: str | list[str],
    idle_timeout: float,
    idle_warning_interval: float | None,
    completion_timeout: float | None = 60.0,
    name: str | None,
    hooks: Hooks,
    timeouts: Timeouts,
    on_event: Callable[[StreamEvent], None] | None,
    logging_cfg: Logging | None,
    signal: AbortSignal,
    prompt_args: Mapping[str, object] | None,
    output: OutputDefinition | None = None,
    resume_session: str | None = None,
    fork_session: bool = False,
    copy_to_worktree: list[str] | None = None,
    throw_on_duplicate_worktree: bool = True,
    existing_worktree: WorktreeHandle | None = None,
    existing_handle: SandboxHandle | None = None,
) -> RunResult:
    wt, caller_managed = prepare_loop_worktree(
        sandbox=sandbox,
        setup=setup,
        branch_strategy=branch_strategy,
        base_branch=base_branch,
        name=name,
        throw_on_duplicate_worktree=throw_on_duplicate_worktree,
        git_timeout=timeouts.git_setup,
        existing_worktree=existing_worktree,
        existing_handle=existing_handle,
    )

    resources = prepare_loop_run_resources(
        setup=setup,
        worktree=wt,
        caller_managed=caller_managed,
        existing_handle=existing_handle,
        git_timeout=timeouts.git_setup,
    )
    unregister_shutdown: Callable[[], None] | None = None

    session_context = prepare_loop_session_context(
        agent=agent,
        sandbox=sandbox,
        worktree=wt,
        max_iterations=max_iterations,
        caller_managed=caller_managed,
    )

    try:
        runtime = start_loop_runtime(
            agent=agent,
            sandbox=sandbox,
            setup=setup,
            worktree=wt,
            caller_managed=caller_managed,
            existing_handle=resources.handle,
            copy_to_worktree=copy_to_worktree,
            hooks=hooks,
            timeouts=timeouts,
            extra_mounts=session_context.extra_mounts,
            name=name,
            target_branch=resources.target_branch,
            logging_cfg=logging_cfg,
            signal=signal,
        )
        resources.handle = runtime.handle
        unregister_shutdown = runtime.unregister_shutdown
        resources.logger = runtime.logger
        log_path = runtime.log_path
        flox_env_dir = runtime.flox_env_dir
        assert resources.logger is not None
        run_loop_iterations(
            max_iterations=max_iterations,
            agent=agent,
            setup=setup,
            worktree=wt,
            resources=resources,
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
            logger=resources.logger,
            on_event=on_event,
            signal=signal,
            session_storage=session_context.storage,
            log_path=log_path,
        )
        finalize_loop_sandbox(
            handle=resources.handle,
            worktree=wt,
            agent_name=agent.name,
            iteration_count=len(resources.iterations),
            logger=resources.logger,
        )

    finally:
        resources.collected_commits, preserved = close_loop_resources(
            unregister_shutdown=unregister_shutdown,
            handle=resources.handle,
            caller_managed=caller_managed,
            hooks=hooks,
            worktree=wt,
            env=setup.merged_env,
            timeouts=timeouts,
            logger=resources.logger,
            commit_base_sha=resources.commit_base_sha,
            completion_hit=resources.completion_hit,
            iteration_count=len(resources.iterations),
            run_span=session_context.run_span,
            stack=session_context.stack,
        )

    return build_loop_result(
        iterations=resources.iterations,
        completion_hit=resources.completion_hit,
        branch=wt.branch,
        stdout_chunks=resources.stdout_chunks,
        worktree_path=wt.worktree_path,
        preserved_worktree_path=preserved,
        cwd=setup.cwd,
        prompt=resources.rendered_prompt,
        env=setup.merged_env,
        log_file_path=log_path,
        commits=resources.collected_commits,
        output=output,
        agent=agent,
        sandbox=sandbox,
    )
