"""Orchestrator iteration loop driver."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import ExitStack
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from eden._types import Iteration, RunResult, Timeouts, Usage
from eden.abort import AbortSignal
from eden.agents._context import IterationContext
from eden.agents._errors import parse_stdout_error
from eden.agents._protocol import Agent
from eden.errors import AgentError, SessionCaptureFailed
from eden.lifecycle import HookPhase, Hooks
from eden.lifecycle._runner import run_host_hooks, run_sandbox_hooks
from eden.logging._config import Logging
from eden.logging._file import FileLogSink, default_log_path
from eden.orchestrator._completion import match
from eden.orchestrator._idle import IdleWatchdog
from eden.orchestrator._result import assemble
from eden.orchestrator._runner import _AgentRunner
from eden.orchestrator._setup import (
    SetupResult,
    resolve_branch_strategy,
    resolve_target_branch,
)
from eden.orchestrator._summary import (
    format_context_window_line,
)
from eden.orchestrator._summary import (
    format_finalize_line as _format_finalize_line,
)
from eden.output import OutputDefinition, extract_structured_output
from eden.prompt import render_prompt
from eden.providers._protocols import SandboxHandle, SandboxProvider
from eden.providers._types import BranchStrategy, CreateOptions, Mount
from eden.sandboxes.errors import UnsupportedStrategy
from eden.session import capture_session
from eden.streaming import StreamEvent
from eden.tracing import set_attributes, span
from eden.worktree._create import WorktreeHandle, create_worktree


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _claude_projects_mount() -> tuple[Mount, ...]:
    """Inject ~/.claude/projects/ → /root/.claude/projects/ when the agent
    needs session capture inside a containerized sandbox.

    no_sandbox ignores the mount; docker honors it. If ~/.claude/projects/
    doesn't exist on the host yet, return () — Claude Code will create it
    on first use, but Eden cannot mount a non-existent path.
    """
    host_dir = Path.home() / ".claude" / "projects"
    if not host_dir.exists():
        return ()
    return (Mount(host=host_dir, sandbox=Path("/root/.claude/projects")),)


def _run_loop(
    *,
    agent: Agent,
    sandbox: SandboxProvider,
    setup: SetupResult,
    branch_strategy: BranchStrategy | None,
    max_iterations: int,
    completion_signal: str | list[str],
    idle_timeout: float,
    idle_warning_interval: float | None,
    name: str | None,
    hooks: Hooks,
    timeouts: Timeouts,
    on_event: Callable[[StreamEvent], None] | None,
    logging_cfg: Logging | None,
    signal: AbortSignal,
    prompt_args: Mapping[str, str] | None,
    output: OutputDefinition | None = None,
    resume_session: str | None = None,
    existing_worktree: WorktreeHandle | None = None,
    existing_handle: SandboxHandle | None = None,
) -> RunResult:
    # Caller-managed mode: when both ``existing_worktree`` and
    # ``existing_handle`` are provided, the loop reuses them and skips both
    # creation and teardown — used by ``Sandbox.run()`` so multiple agents
    # can share one container and one branch.
    caller_managed = existing_worktree is not None and existing_handle is not None
    if caller_managed:
        assert existing_worktree is not None
        wt: WorktreeHandle = existing_worktree
        if branch_strategy is not None:
            from eden.errors import InvalidOptions

            raise InvalidOptions(
                code="config.invalid_options",
                message=(
                    "branch_strategy is incompatible with caller-managed runs; "
                    "the sandbox already owns its worktree and branch"
                ),
            )
    else:
        strategy = resolve_branch_strategy(
            branch_strategy=branch_strategy,
            sandbox_kind=sandbox.kind,
        )
        if not sandbox.supports_strategy(strategy):
            raise UnsupportedStrategy(provider=sandbox.name, strategy=strategy.tag)
        wt = create_worktree(host_repo_path=setup.cwd, strategy=strategy, name_hint=name)

    target_branch = resolve_target_branch(host_repo_path=setup.cwd)

    sink: FileLogSink | None = None
    handle: SandboxHandle | None = existing_handle if caller_managed else None
    iterations: list[Iteration] = []
    stdout_chunks: list[str] = []
    completion_hit: str | None = None
    rendered_prompt = ""
    log_path: Path | None = None
    preserved: Path | None = None

    captures = bool(getattr(agent, "captures_sessions", False))
    extra_mounts: tuple[Mount, ...] = _claude_projects_mount() if captures else ()

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
        if not caller_managed:
            run_host_hooks(
                phase=HookPhase.OnWorktreeReady,
                hooks=hooks.host,
                worktree_path=wt.worktree_path,
                env=setup.merged_env,
                timeouts=timeouts,
            )

        signal.raise_if_aborted()

        if not caller_managed:
            with span(
                "eden.sandbox.create",
                attributes={
                    "sandbox.name": sandbox.name,
                    "sandbox.kind": sandbox.kind,
                    "branch": wt.branch,
                },
            ):
                handle = sandbox.create(
                    CreateOptions(
                        branch=wt.branch,
                        worktree_path=wt.worktree_path,
                        host_repo_path=wt.host_repo_path,
                        env=setup.merged_env,
                        mounts=extra_mounts,
                        name_hint=name,
                    )
                )
                run_sandbox_hooks(
                    phase=HookPhase.OnSandboxReady,
                    hooks=hooks.sandbox,
                    handle=handle,
                    env=setup.merged_env,
                    timeouts=timeouts,
                )
        assert handle is not None

        log_cfg = logging_cfg or Logging.file(
            default_log_path(
                host_repo_path=setup.cwd,
                branch=wt.branch,
            )
        )
        log_path = log_cfg.path
        sink = FileLogSink.open(
            log_cfg.path,
            level=log_cfg.level,
            env_values=tuple(setup.merged_env.values()),
        )
        agent_stream_cb = log_cfg.on_agent_stream_event

        def _forward_agent_event(ev: StreamEvent) -> None:
            """Fire ``Logging.on_agent_stream_event`` for agent-derived events.

            Errors raised by the callback are swallowed so a broken forwarder
            cannot kill the run.
            """
            if agent_stream_cb is None:
                return
            if ev.type not in ("text", "tool_call", "usage"):
                return
            try:
                agent_stream_cb(ev)
            except Exception:
                pass

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
                )
            )

            wd = IdleWatchdog(
                idle_timeout=idle_timeout,
                idle_warning_interval=idle_warning_interval,
            )
            wd.start()
            try:
                iter_completion: str | None = None
                agent_cwd = handle.worktree_path if handle.worktree_path.exists() else None
                # Optional stdin payload — agents that override prompt
                # delivery (e.g. claude_code, to dodge the 128 KB execve
                # arg limit on Linux) implement ``stdin_content(ctx)``.
                stdin_fn = getattr(agent, "stdin_content", None)
                stdin_payload = (
                    stdin_fn(
                        IterationContext(
                            iteration=i,
                            prompt=rendered_prompt,
                            sandbox_handle=handle,
                            worktree_path=wt.worktree_path,
                            branch=wt.branch,
                            name=name,
                            resume_session=resume_session,
                        )
                    )
                    if callable(stdin_fn)
                    else None
                )
                with (
                    span(
                        "eden.agent.exec",
                        attributes={
                            "agent.name": agent.name,
                            "agent.model": getattr(agent, "model", None),
                            "iteration.index": i,
                            "branch": wt.branch,
                        },
                    ),
                    _AgentRunner(
                        argv=argv,
                        env=setup.merged_env,
                        watchdog=wd,
                        cwd=agent_cwd,
                        stdin=stdin_payload,
                    ) as runner,
                ):

                    def _emit_warning(minutes: int, _i: int = i) -> None:
                        ev = StreamEvent(
                            type="idle_warning",
                            agent_name=agent.name,
                            iteration=_i,
                            timestamp=_utcnow(),
                            minutes_idle=minutes,
                        )
                        if sink is not None:
                            sink.write(ev)
                        if on_event is not None:
                            on_event(ev)

                    for line in runner.iter_lines(signal=signal, on_warning=_emit_warning):
                        stdout_chunks.append(line + "\n")
                        parsed = agent.parse_stream(line)
                        if parsed is not None:
                            # Parser doesn't know the real iteration; rewrap.
                            ev = replace(parsed, iteration=i, agent_name=agent.name)
                        else:
                            ev = StreamEvent(
                                type="text",
                                agent_name=agent.name,
                                iteration=i,
                                timestamp=_utcnow(),
                                text=line,
                            )
                        if ev.type == "usage":
                            iter_session_id = ev.session_id
                            iter_usage = ev.usage
                        if sink is not None:
                            sink.write(ev)
                        if on_event is not None:
                            on_event(ev)
                        _forward_agent_event(ev)
                        hit = match(line, completion_signal)
                        if hit is not None:
                            iter_completion = hit
                            # Drain any trailing lines before terminating so that
                            # the agent's final ``result`` line (carrying
                            # session_id + usage) is captured even when the
                            # completion signal fires before the process exits.
                            for trailing in runner.drain_remaining():
                                stdout_chunks.append(trailing + "\n")
                                trailing_parsed = agent.parse_stream(trailing)
                                if trailing_parsed is not None:
                                    tev = replace(
                                        trailing_parsed,
                                        iteration=i,
                                        agent_name=agent.name,
                                    )
                                    if tev.type == "usage":
                                        iter_session_id = tev.session_id
                                        iter_usage = tev.usage
                                    if sink is not None:
                                        sink.write(tev)
                                    if on_event is not None:
                                        on_event(tev)
                                    _forward_agent_event(tev)
                            runner.terminate()
                            break
            finally:
                wd.stop()

            # Agent process EOFed without matching the completion signal.
            # If it exited non-zero, surface the failure as a typed
            # ``AgentError`` rather than letting the loop wait for an
            # idle/iteration timeout. ``parse_stdout_error`` extracts the
            # message body for Codex / Pi / OpenCode, which emit error
            # events on stdout instead of stderr.
            if iter_completion is None:
                rc = runner.exit_code()
                if rc is not None and rc != 0:
                    parsed_stdout: str | None = parse_stdout_error("".join(stdout_chunks))
                    stderr_text = runner.stderr_text.strip()
                    body = parsed_stdout or stderr_text or "(no output)"
                    raise AgentError(
                        message=(
                            f"agent {agent.name!r} exited with code {rc} "
                            f"on iteration {i} without a completion signal: {body}"
                        ),
                        hint=(
                            "check the agent's stdout/stderr in the run log; for "
                            "claude-code, ensure the prompt requests a "
                            "<promise>COMPLETE</promise> tag"
                        ),
                        agent_name=agent.name,
                        exit_code=rc,
                        stderr=stderr_text,
                        parsed_error=parsed_stdout,
                    )

            if iter_session_id is not None and captures:
                try:
                    # ``sandbox_cwd`` is the working directory Claude Code sees
                    # when it writes its session JSONL.  For no_sandbox the
                    # agent subprocess inherits the host CWD (host_repo_path);
                    # for container-based sandboxes, handle.worktree_path holds
                    # the in-container path (e.g. /workspace).  Use
                    # host_repo_path when the handle's worktree_path lives
                    # inside host_repo_path (i.e. no_sandbox / native
                    # execution), otherwise use the handle's own path.
                    if (
                        wt.host_repo_path in handle.worktree_path.parents
                        or handle.worktree_path == wt.host_repo_path
                    ):
                        effective_sandbox_cwd = wt.host_repo_path
                    else:
                        effective_sandbox_cwd = handle.worktree_path
                    # Store session files under the target branch name so all
                    # iterations for a given target are co-located.
                    iter_session_file = capture_session(
                        session_id=iter_session_id,
                        sandbox_cwd=effective_sandbox_cwd,
                        host_repo_path=setup.cwd,
                        branch=target_branch,
                        iteration=i,
                    )
                except SessionCaptureFailed as exc:
                    if sink is not None:
                        sink.write(
                            StreamEvent(
                                type="text",
                                agent_name=agent.name,
                                iteration=i,
                                timestamp=_utcnow(),
                                text=f"[eden] session capture failed: {exc}",
                            )
                        )

            if iter_usage is not None:
                ctx_ev = StreamEvent(
                    type="text",
                    agent_name=agent.name,
                    iteration=i,
                    timestamp=_utcnow(),
                    text=format_context_window_line(iter_usage),
                )
                if sink is not None:
                    sink.write(ctx_ev)
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

        # Phase 4a: post-iteration finalize for isolated providers.
        if handle is not None and hasattr(handle, "finalize"):
            try:
                fr = handle.finalize(target=wt.host_repo_path)
                if sink is not None:
                    sink.write(
                        StreamEvent(
                            type="text",
                            agent_name=agent.name,
                            iteration=len(iterations),
                            timestamp=_utcnow(),
                            text=_format_finalize_line(fr),
                        )
                    )
            except Exception as exc:
                if sink is not None:
                    sink.write(
                        StreamEvent(
                            type="text",
                            agent_name=agent.name,
                            iteration=len(iterations),
                            timestamp=_utcnow(),
                            text=f"[eden] finalize failed: {exc}",
                        )
                    )

    finally:
        if handle is not None and not caller_managed:
            try:
                run_sandbox_hooks(
                    phase=HookPhase.OnClose,
                    hooks=hooks.sandbox,
                    handle=handle,
                    env=setup.merged_env,
                    timeouts=timeouts,
                )
            except Exception:
                pass
        if not caller_managed:
            try:
                run_host_hooks(
                    phase=HookPhase.OnClose,
                    hooks=hooks.host,
                    worktree_path=wt.worktree_path,
                    env=setup.merged_env,
                    timeouts=timeouts,
                )
            except Exception:
                pass
        if handle is not None and not caller_managed:
            try:
                handle.close()
            except Exception:
                pass
        if sink is not None:
            sink.close()
        if not caller_managed:
            close_result = wt.close()
            if close_result.action == "preserved":
                preserved = wt.worktree_path
        # Record the final outcome on the eden.run span, then close the
        # ExitStack (which exits the span). Done after the rest of cleanup
        # so the span reflects the full lifecycle including hook teardown.
        set_attributes(
            run_span,
            {
                "iterations": len(iterations),
                "completion_signal": completion_hit,
            },
        )
        _stack.close()

    last = iterations[-1] if iterations else None
    full_stdout = "".join(stdout_chunks)
    extracted: object | None = None
    if output is not None:
        extracted = extract_structured_output(
            full_stdout,
            output,
            branch=wt.branch,
            preserved_worktree_path=preserved,
        )
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
        output=extracted,
    )


__all__ = ["_run_loop"]
