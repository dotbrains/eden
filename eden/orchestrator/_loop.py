"""Orchestrator iteration loop driver."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from contextlib import ExitStack
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from eden._types import Commit, Iteration, RunResult, Timeouts, Usage

if TYPE_CHECKING:
    from eden.session._protocol import SessionStorage
from eden.abort import AbortSignal, register_shutdown
from eden.agents._context import IterationContext
from eden.agents._errors import parse_stdout_error
from eden.agents._flox import flox_wrap, validate_flox_env
from eden.agents._protocol import Agent
from eden.errors import AgentError, SessionCaptureFailed
from eden.lifecycle import HookPhase, Hooks
from eden.lifecycle._runner import run_host_hooks, run_sandbox_hooks
from eden.logging._config import Logging
from eden.logging._file import FileLogSink, default_log_path
from eden.logging._stdout import StdoutLogSink
from eden.orchestrator._bounded_tail import BoundedTail
from eden.orchestrator._completion import match
from eden.orchestrator._copy_files import apply_copy_to_worktree
from eden.orchestrator._finalize_recovery import format_finalize_recovery
from eden.orchestrator._idle import IdleWatchdog
from eden.orchestrator._recovery import format_agent_error_recovery
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
from eden.streaming import StreamEvent
from eden.tracing import set_attributes, span
from eden.worktree._create import WorktreeHandle, create_worktree
from eden.worktree._git import head_sha, new_commits

# Slack subtracted from an iteration's start time before scoping the subagent
# transcript sweep, to tolerate second-granularity mtime truncation on some
# filesystems (a file written at start+0.4s can report an mtime floored below
# the fractional start instant).
_SIDECHAIN_MTIME_SLACK = 2.0


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _resolve_session_storage(agent: Agent) -> SessionStorage | None:
    """Return the agent's ``session_storage`` attribute, or fall back to the
    legacy ``captures_sessions`` boolean (claude_code only).

    ADR-0012-style: agents that ship a ``session_storage`` get fully custom
    transcript capture (mounts + host_capture + sandbox_transfer). Agents
    that only expose ``captures_sessions=True`` get the
    :class:`ClaudeSessionStorage` default, matching the pre-ADR behaviour.
    """
    storage: SessionStorage | None = getattr(agent, "session_storage", None)
    if storage is not None:
        return storage
    if getattr(agent, "captures_sessions", False):
        # Lazy import to avoid module-load cycle with eden.session.
        from eden.session._claude import ClaudeSessionStorage

        return ClaudeSessionStorage()
    return None


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
            base_branch=base_branch,
        )
        if not sandbox.supports_strategy(strategy):
            raise UnsupportedStrategy(provider=sandbox.name, strategy=strategy.tag)
        wt = create_worktree(
            host_repo_path=setup.cwd,
            strategy=strategy,
            name_hint=name,
            throw_on_duplicate_worktree=throw_on_duplicate_worktree,
            git_timeout=timeouts.git_setup,
        )

    target_branch = resolve_target_branch(host_repo_path=setup.cwd)

    # Snapshot the branch tip before the agent runs so the post-run
    # ``git rev-list base..HEAD`` census attributes only this run's commits
    # (a caller-managed worktree may already carry commits from earlier
    # agents in the same sandbox). Best-effort: "" disables the census.
    commit_base_sha = head_sha(repo_path=wt.worktree_path, timeout=timeouts.git_setup)
    collected_commits: list[Commit] = []

    sink: FileLogSink | StdoutLogSink | None = None
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

    session_storage = _resolve_session_storage(agent)
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
        if not caller_managed:
            # Seed user-supplied files into the worktree before
            # ``on_worktree_ready`` hooks fire — hooks may depend on the
            # copied files (e.g. an ``npm install`` hook reading ``.env``).
            apply_copy_to_worktree(
                paths=copy_to_worktree,
                source_root=setup.cwd,
                worktree_path=wt.worktree_path,
            )
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

        # SIGTERM doesn't run try/finally — register an emergency cleanup so
        # containers and worktrees don't leak when the parent dies abruptly.
        # The normal-exit path unregisters this in `finally` before its own
        # close, so close() runs once on the happy path.
        if not caller_managed:
            _emergency_handle = handle
            _emergency_wt = wt

            def _emergency_cleanup() -> None:
                try:
                    _emergency_handle.close()
                except Exception:
                    pass
                try:
                    _emergency_wt.close()
                except Exception:
                    pass

            unregister_shutdown = register_shutdown(_emergency_cleanup)

        log_cfg = logging_cfg or Logging.file(
            default_log_path(
                host_repo_path=setup.cwd,
                branch=wt.branch,
                target_branch=target_branch,
                name=name,
            )
        )
        if log_cfg.type == "file" and log_cfg.path is not None:
            log_path = log_cfg.path
            sink = FileLogSink.open(
                log_cfg.path,
                level=log_cfg.level,
                env_values=tuple(setup.merged_env.values()),
            )
        else:
            # Logging.stdout() — no log file; RunResult.log_file_path stays None.
            sink = StdoutLogSink(
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
            if ev.type not in ("text", "tool_call", "usage", "session_id", "raw"):
                return
            try:
                agent_stream_cb(ev)
            except Exception:
                pass

        # Per-agent Flox runtime (ADR-0014): resolve + validate once so a
        # dangling flox_env fails before the first iteration, then wrap each
        # iteration's argv in ``flox activate -d <dir> -- <argv>``.
        _raw_flox_env = getattr(agent, "flox_env", None)
        flox_env_dir = validate_flox_env(_raw_flox_env) if _raw_flox_env is not None else None

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

            wd = IdleWatchdog(
                idle_timeout=idle_timeout,
                idle_warning_interval=idle_warning_interval,
            )
            wd.start()
            try:
                iter_completion: str | None = None
                agent_exit_code: int | None = None
                agent_stderr: str = ""
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

                    def _emit_raw(raw_line: str, _i: int = i) -> None:
                        """Surface the literal stdout line as a ``raw`` event.

                        Only when ``Logging(verbose=True)``; written to the log
                        and forwarded to ``on_agent_stream_event`` (not the
                        generic ``on_event``, which already carries the parsed
                        ``text`` event for unparsed lines).
                        """
                        if not log_cfg.verbose:
                            return
                        rev = StreamEvent(
                            type="raw",
                            agent_name=agent.name,
                            iteration=_i,
                            timestamp=_utcnow(),
                            text=raw_line,
                        )
                        if sink is not None:
                            sink.write(rev)
                        _forward_agent_event(rev)

                    for line in runner.iter_lines(signal=signal, on_warning=_emit_warning):
                        stdout_chunks.push(line + "\n")
                        _emit_raw(line)
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
                        elif ev.type == "session_id":
                            iter_session_id = ev.session_id
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
                            # ``completion_timeout`` bounds the total wait so a
                            # child process that holds the pipe open after the
                            # agent emits the signal can't hang the loop until
                            # the much-larger ``idle_timeout`` trips.
                            drain = runner.drain_remaining(total_timeout=completion_timeout)
                            if drain.timed_out and sink is not None:
                                warn_ev = StreamEvent(
                                    type="text",
                                    agent_name=agent.name,
                                    iteration=i,
                                    timestamp=_utcnow(),
                                    text=(
                                        f"[eden] completion_timeout ({completion_timeout}s) "
                                        "elapsed after completion signal — agent process did "
                                        "not EOF; terminating now. Iteration succeeded."
                                    ),
                                )
                                sink.write(warn_ev)
                                if on_event is not None:
                                    on_event(warn_ev)
                            for trailing in drain.lines:
                                stdout_chunks.push(trailing + "\n")
                                _emit_raw(trailing)
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
                                    elif tev.type == "session_id":
                                        iter_session_id = tev.session_id
                                    if sink is not None:
                                        sink.write(tev)
                                    if on_event is not None:
                                        on_event(tev)
                                    _forward_agent_event(tev)
                            runner.terminate()
                            break
                    # Capture exit code BEFORE the with-block's __exit__ runs
                    # ``terminate()`` and nulls the process handle. Only used
                    # when ``iter_completion`` stays ``None`` below.
                    agent_exit_code = runner.exit_code()
                    agent_stderr = runner.stderr_text
            finally:
                wd.stop()

            # Agent process EOFed without matching the completion signal.
            # If it exited non-zero, surface the failure as a typed
            # ``AgentError`` rather than letting the loop wait for an
            # idle/iteration timeout. ``parse_stdout_error`` extracts the
            # message body for Codex / Pi / OpenCode, which emit error
            # events on stdout instead of stderr.
            if iter_completion is None:
                if agent_exit_code is not None and agent_exit_code != 0:
                    parsed_stdout: str | None = parse_stdout_error(stdout_chunks.to_string())
                    stderr_text = agent_stderr.strip()
                    body = parsed_stdout or stderr_text or "(no output)"
                    err = AgentError(
                        message=(
                            f"agent {agent.name!r} exited with code {agent_exit_code} "
                            f"on iteration {i} without a completion signal: {body}"
                        ),
                        hint=(
                            "check the agent's stdout/stderr in the run log; for "
                            "claude-code, ensure the prompt requests a "
                            "<promise>COMPLETE</promise> tag"
                        ),
                        agent_name=agent.name,
                        exit_code=agent_exit_code,
                        stderr=stderr_text,
                        parsed_error=parsed_stdout,
                    )
                    # Emit a copy-pastable recovery hint via the sink so it
                    # lands in the run log even if the caller catches the
                    # exception silently.
                    recovery_text = format_agent_error_recovery(
                        error=err,
                        branch=wt.branch,
                        worktree_path=wt.worktree_path,
                        log_path=log_path,
                    )
                    recovery_ev = StreamEvent(
                        type="text",
                        agent_name=agent.name,
                        iteration=i,
                        timestamp=_utcnow(),
                        text=recovery_text,
                    )
                    if sink is not None:
                        sink.write(recovery_ev)
                    if on_event is not None:
                        on_event(recovery_ev)
                    raise err

            if iter_session_id is not None and session_storage is not None:
                try:
                    # Delegate to the agent's session storage. Each agent
                    # knows where its own transcript lives; the orchestrator
                    # only knows the metadata (id, branch, iteration).
                    # ``target_branch`` is preferred over ``wt.branch`` so
                    # all iterations for one target land under the same
                    # directory regardless of which intermediate branch the
                    # worktree carved.
                    iter_session_file = session_storage.host_capture(
                        handle=handle,
                        session_id=iter_session_id,
                        host_repo_path=setup.cwd,
                        branch=target_branch,
                        iteration=i,
                        since=iter_started_at,
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
                _preserve = getattr(handle, "preserve", None)
                if callable(_preserve):
                    try:
                        _preserve()
                    except Exception:
                        pass
                if sink is not None:
                    recovery = format_finalize_recovery(
                        isolated_path=handle.worktree_path,
                        target_path=wt.host_repo_path,
                        error=exc,
                        preserved=callable(_preserve),
                    )
                    sink.write(
                        StreamEvent(
                            type="text",
                            agent_name=agent.name,
                            iteration=len(iterations),
                            timestamp=_utcnow(),
                            text=recovery,
                        )
                    )
            else:
                if not fr.applied and sink is not None:
                    _preserve = getattr(handle, "preserve", None)
                    if callable(_preserve):
                        try:
                            _preserve()
                        except Exception:
                            pass
                    recovery = format_finalize_recovery(
                        isolated_path=handle.worktree_path,
                        target_path=wt.host_repo_path,
                        files_failed=fr.files_changed,
                        preserved=callable(_preserve),
                    )
                    sink.write(
                        StreamEvent(
                            type="text",
                            agent_name=agent.name,
                            iteration=len(iterations),
                            timestamp=_utcnow(),
                            text=recovery,
                        )
                    )

    finally:
        if unregister_shutdown is not None:
            try:
                unregister_shutdown()
            except Exception:
                pass
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
        # Census the agent's commits while the worktree is still on disk —
        # ``wt.close()`` below may remove it. Runs for caller-managed runs
        # too (their worktree outlives this loop but the SHAs are this run's).
        collected_commits = [
            Commit(sha=sha)
            for sha in new_commits(
                worktree_path=wt.worktree_path,
                base_sha=commit_base_sha,
                timeout=timeouts.commit_collection,
            )
        ]
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
