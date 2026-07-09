"""Orchestrator iteration loop driver."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import ExitStack
from datetime import UTC, datetime
from pathlib import Path

from eden._types import Commit, Iteration, RunResult, Timeouts
from eden.abort import AbortSignal
from eden.agents._protocol import Agent
from eden.lifecycle import Hooks
from eden.logging._config import Logging
from eden.orchestrator._finalize import finalize_sandbox
from eden.orchestrator._logging import LoopLogger
from eden.orchestrator._loop_cleanup import close_loop_resources
from eden.orchestrator._loop_iteration import run_loop_iteration
from eden.orchestrator._loop_resources import prepare_loop_worktree
from eden.orchestrator._loop_startup import start_loop_runtime
from eden.orchestrator._result import assemble
from eden.orchestrator._session_capture import resolve_session_storage
from eden.orchestrator._setup import (
    SetupResult,
    resolve_target_branch,
)
from eden.output import OutputDefinition, extract_structured_output
from eden.providers._protocols import SandboxHandle, SandboxProvider
from eden.providers._types import BranchStrategy, Mount
from eden.streaming import StreamEvent
from eden.streaming._bounded_tail import BoundedTail
from eden.tracing import span
from eden.worktree._create import WorktreeHandle
from eden.worktree._git import head_sha


def _utcnow() -> datetime:
    return datetime.now(UTC)


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
    prompt_args: Mapping[str, str] | None,
    output: OutputDefinition | None = None,
    resume_session: str | None = None,
    fork_session: bool = False,
    copy_to_worktree: list[str] | None = None,
    throw_on_duplicate_worktree: bool = True,
    existing_worktree: WorktreeHandle | None = None,
    existing_handle: SandboxHandle | None = None,
) -> RunResult:
    # Caller-managed mode: when both ``existing_worktree`` and
    # ``existing_handle`` are provided, the loop reuses them and skips both
    # creation and teardown — used by ``Sandbox.run()`` so multiple agents
    # can share one container and one branch.
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

    target_branch = resolve_target_branch(host_repo_path=setup.cwd)

    # Snapshot the branch tip before the agent runs so the post-run
    # ``git rev-list base..HEAD`` census attributes only this run's commits
    # (a caller-managed worktree may already carry commits from earlier
    # agents in the same sandbox). Best-effort: "" disables the census.
    commit_base_sha = head_sha(repo_path=wt.worktree_path, timeout=timeouts.git_setup)
    collected_commits: list[Commit] = []

    logger: LoopLogger | None = None
    handle: SandboxHandle | None = existing_handle if caller_managed else None
    iterations: list[Iteration] = []
    # Bounded rolling tail — capped to keep memory finite on long agent
    # runs. The three consumers (parse_stdout_error, Output extraction,
    # final RunResult.stdout) all care about the tail, not the head.
    stdout_chunks = BoundedTail()
    completion_hit: str | None = None
    rendered_prompt = ""
    log_path: Path | None = None
    preserved: Path | None = None
    unregister_shutdown: Callable[[], None] | None = None

    session_storage = resolve_session_storage(agent)
    extra_mounts: tuple[Mount, ...] = (
        session_storage.extra_mounts() if session_storage is not None else ()
    )

    # Push the outer ``eden.run`` span via ExitStack so we don't have to
    # re-indent the entire loop body. The span is closed as part of the
    # try/finally cleanup below.
    _stack = ExitStack()
    run_span = _stack.enter_context(
        span(
            "eden.run",
            attributes={
                "agent.name": agent.name,
                "agent.model": getattr(agent, "model", None),
                "sandbox.name": sandbox.name,
                "sandbox.kind": sandbox.kind,
                "branch": wt.branch,
                "max_iterations": max_iterations,
                "caller_managed": caller_managed,
            },
        )
    )

    try:
        runtime = start_loop_runtime(
            agent=agent,
            sandbox=sandbox,
            setup=setup,
            worktree=wt,
            caller_managed=caller_managed,
            existing_handle=handle,
            copy_to_worktree=copy_to_worktree,
            hooks=hooks,
            timeouts=timeouts,
            extra_mounts=extra_mounts,
            name=name,
            target_branch=target_branch,
            logging_cfg=logging_cfg,
            signal=signal,
        )
        handle = runtime.handle
        unregister_shutdown = runtime.unregister_shutdown
        logger = runtime.logger
        log_path = runtime.log_path
        flox_env_dir = runtime.flox_env_dir
        assert logger is not None

        for i in range(max_iterations):
            iteration_result = run_loop_iteration(
                iteration_index=i,
                agent=agent,
                setup=setup,
                worktree=wt,
                target_branch=target_branch,
                handle=handle,
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
                stdout_chunks=stdout_chunks,
                session_storage=session_storage,
                log_path=log_path,
            )
            rendered_prompt = iteration_result.rendered_prompt
            iterations.append(iteration_result.iteration)
            if iteration_result.completion is not None:
                completion_hit = iteration_result.completion
                break

        if handle is not None:
            finalize_sandbox(
                handle=handle,
                target_path=wt.host_repo_path,
                agent_name=agent.name,
                iteration=len(iterations),
                timestamp=_utcnow,
                sink=logger.sink if logger is not None else None,
            )

    finally:
        collected_commits, preserved = close_loop_resources(
            unregister_shutdown=unregister_shutdown,
            handle=handle,
            caller_managed=caller_managed,
            hooks=hooks,
            worktree=wt,
            env=setup.merged_env,
            timeouts=timeouts,
            logger=logger,
            commit_base_sha=commit_base_sha,
            completion_hit=completion_hit,
            iteration_count=len(iterations),
            run_span=run_span,
            stack=_stack,
        )

    last = iterations[-1] if iterations else None
    full_stdout = stdout_chunks.to_string()
    extracted: object | None = None
    if output is not None:
        extracted = extract_structured_output(
            full_stdout,
            output,
            branch=wt.branch,
            preserved_worktree_path=preserved,
            session_id=last.session_id if last else None,
            session_file_path=last.session_file_path if last else None,
        )
    from eden._types import _RunContext

    return assemble(
        iterations=iterations,
        completion_signal=completion_hit,
        branch=wt.branch,
        stdout=full_stdout,
        worktree_path=wt.worktree_path,
        preserved_worktree_path=preserved,
        cwd=setup.cwd,
        prompt=rendered_prompt,
        env=setup.merged_env,
        log_file_path=log_path,
        session_id=last.session_id if last else None,
        session_file_path=last.session_file_path if last else None,
        usage=last.usage if last else None,
        commits=collected_commits,
        output=extracted,
        ctx=_RunContext(agent=agent, sandbox=sandbox, cwd=setup.cwd),
    )


__all__ = ["_run_loop"]
