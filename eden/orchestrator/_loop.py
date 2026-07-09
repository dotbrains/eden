"""Orchestrator iteration loop driver."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from contextlib import ExitStack
from datetime import UTC, datetime
from pathlib import Path

from eden._types import Commit, Iteration, RunResult, Timeouts, Usage
from eden.abort import AbortSignal
from eden.agents._context import IterationContext
from eden.agents._flox import flox_wrap
from eden.agents._protocol import Agent
from eden.lifecycle import HookPhase, Hooks
from eden.lifecycle._runner import run_host_hooks, run_sandbox_hooks
from eden.logging._config import Logging
from eden.orchestrator._agent_exec import execute_agent_iteration
from eden.orchestrator._agent_failure import raise_agent_exit_without_completion
from eden.orchestrator._finalize import finalize_sandbox
from eden.orchestrator._logging import LoopLogger
from eden.orchestrator._loop_cleanup import close_loop_resources
from eden.orchestrator._loop_resources import prepare_loop_worktree
from eden.orchestrator._loop_startup import start_loop_runtime
from eden.orchestrator._result import assemble
from eden.orchestrator._session_capture import capture_iteration_session, resolve_session_storage
from eden.orchestrator._setup import (
    SetupResult,
    resolve_target_branch,
)
from eden.orchestrator._summary import (
    format_context_window_line,
)
from eden.output import OutputDefinition, extract_structured_output
from eden.prompt import render_prompt
from eden.providers._protocols import SandboxHandle, SandboxProvider
from eden.providers._types import BranchStrategy, Mount
from eden.streaming import StreamEvent
from eden.streaming._bounded_tail import BoundedTail
from eden.tracing import span
from eden.worktree._create import WorktreeHandle
from eden.worktree._git import head_sha

# Slack subtracted from an iteration's start time before scoping the subagent
# transcript sweep, to tolerate second-granularity mtime truncation on some
# filesystems (a file written at start+0.4s can report an mtime floored below
# the fractional start instant).
_SIDECHAIN_MTIME_SLACK = 2.0


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

        for i in range(max_iterations):
            signal.raise_if_aborted()
            iter_session_id: str | None = None
            iter_usage: Usage | None = None
            iter_session_file: Path | None = None

            run_host_hooks(
                phase=HookPhase.OnIterationStart,
                hooks=hooks.host,
                worktree_path=wt.worktree_path,
                env=setup.merged_env,
                timeouts=timeouts,
            )
            run_sandbox_hooks(
                phase=HookPhase.OnIterationStart,
                hooks=hooks.sandbox,
                handle=handle,
                env=setup.merged_env,
                timeouts=timeouts,
            )

            if setup.prompt_is_literal:
                # Inline prompts (``prompt="..."``) are passed to the agent
                # verbatim — no ``{{KEY}}`` substitution, no ``!`cmd``` shell
                # expansion, no built-in branch injection.
                rendered_prompt = setup.prompt_text
            else:
                rendered_prompt = render_prompt(
                    text=setup.prompt_text,
                    args=prompt_args or {},
                    source_branch=wt.branch,
                    target_branch=target_branch,
                    handle=handle,
                )

            argv = agent.build_command(
                IterationContext(
                    iteration=i,
                    prompt=rendered_prompt,
                    sandbox_handle=handle,
                    worktree_path=wt.worktree_path,
                    branch=wt.branch,
                    name=name,
                    resume_session=resume_session,
                    fork_session=fork_session,
                )
            )
            argv = flox_wrap(argv, flox_env=flox_env_dir)

            # Wall-clock start of this iteration's agent, used to scope the
            # subagent/sidechain transcript sweep to this run. A small slack
            # absorbs second-granularity mtime truncation on some filesystems
            # so a transcript written moments after start isn't dropped.
            iter_started_at = time.time() - _SIDECHAIN_MTIME_SLACK

            agent_execution = execute_agent_iteration(
                agent=agent,
                argv=argv,
                env=setup.merged_env,
                handle=handle,
                worktree_path=wt.worktree_path,
                branch=wt.branch,
                name=name,
                resume_session=resume_session,
                rendered_prompt=rendered_prompt,
                iteration=i,
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
            iter_completion = agent_execution.completion
            agent_exit_code = agent_execution.exit_code
            agent_stderr = agent_execution.stderr
            iter_session_id = agent_execution.session_id
            iter_usage = agent_execution.usage

            # Agent process EOFed without matching the completion signal.
            # If it exited non-zero, surface the failure as a typed
            # ``AgentError`` rather than letting the loop wait for an
            # idle/iteration timeout. ``parse_stdout_error`` extracts the
            # message body for Codex / Pi / OpenCode, which emit error
            # events on stdout instead of stderr.
            if iter_completion is None:
                if agent_exit_code is not None and agent_exit_code != 0:
                    raise_agent_exit_without_completion(
                        agent_name=agent.name,
                        iteration=i,
                        exit_code=agent_exit_code,
                        stderr=agent_stderr,
                        stdout=stdout_chunks.to_string(),
                        branch=wt.branch,
                        worktree_path=wt.worktree_path,
                        log_path=log_path,
                        sink=logger.sink if logger is not None else None,
                        on_event=on_event,
                        timestamp=_utcnow,
                    )

            iter_session_file = capture_iteration_session(
                session_storage=session_storage,
                handle=handle,
                session_id=iter_session_id,
                host_repo_path=setup.cwd,
                target_branch=target_branch,
                iteration=i,
                since=iter_started_at,
                agent_name=agent.name,
                timestamp=_utcnow(),
                sink=logger.sink if logger is not None else None,
            )

            if iter_usage is not None:
                ctx_ev = StreamEvent(
                    type="text",
                    agent_name=agent.name,
                    iteration=i,
                    timestamp=_utcnow(),
                    text=format_context_window_line(iter_usage),
                )
                if logger is not None:
                    logger.write(ctx_ev)
                if on_event is not None:
                    on_event(ctx_ev)

            run_sandbox_hooks(
                phase=HookPhase.OnIterationEnd,
                hooks=hooks.sandbox,
                handle=handle,
                env=setup.merged_env,
                timeouts=timeouts,
            )
            run_host_hooks(
                phase=HookPhase.OnIterationEnd,
                hooks=hooks.host,
                worktree_path=wt.worktree_path,
                env=setup.merged_env,
                timeouts=timeouts,
            )

            iterations.append(
                Iteration(
                    index=i,
                    completion_signal=iter_completion,
                    session_id=iter_session_id,
                    session_file_path=iter_session_file,
                    usage=iter_usage,
                )
            )
            if iter_completion is not None:
                completion_hit = iter_completion
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
