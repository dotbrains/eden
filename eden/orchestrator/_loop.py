"""Orchestrator iteration loop driver."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from eden._types import Iteration, RunResult, Timeouts, Usage
from eden.abort import AbortSignal
from eden.agents._context import IterationContext
from eden.agents._protocol import Agent
from eden.errors import SessionCaptureFailed
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
from eden.prompt import render_prompt
from eden.providers._protocols import SandboxProvider
from eden.providers._types import BranchStrategy, CreateOptions, Mount
from eden.sandboxes.errors import UnsupportedStrategy
from eden.session import capture_session
from eden.streaming import StreamEvent
from eden.worktree._create import create_worktree


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
) -> RunResult:
    strategy = resolve_branch_strategy(
        branch_strategy=branch_strategy,
        sandbox_kind=sandbox.kind,
    )
    if not sandbox.supports_strategy(strategy):
        raise UnsupportedStrategy(provider=sandbox.name, strategy=strategy.tag)

    target_branch = resolve_target_branch(host_repo_path=setup.cwd)

    wt = create_worktree(host_repo_path=setup.cwd, strategy=strategy, name_hint=name)
    sink: FileLogSink | None = None
    handle = None
    iterations: list[Iteration] = []
    stdout_chunks: list[str] = []
    completion_hit: str | None = None
    rendered_prompt = ""
    log_path: Path | None = None
    preserved: Path | None = None

    captures = bool(getattr(agent, "captures_sessions", False))
    extra_mounts: tuple[Mount, ...] = _claude_projects_mount() if captures else ()

    try:
        run_host_hooks(
            phase=HookPhase.OnWorktreeReady,
            hooks=hooks.host,
            worktree_path=wt.worktree_path,
            env=setup.merged_env,
            timeouts=timeouts,
        )

        signal.raise_if_aborted()

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
                )
            )

            wd = IdleWatchdog(
                idle_timeout=idle_timeout,
                idle_warning_interval=idle_warning_interval,
            )
            wd.start()
            try:
                iter_completion: str | None = None
                with _AgentRunner(argv=argv, env=setup.merged_env, watchdog=wd) as runner:

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
                        hit = match(line, completion_signal)
                        if hit is not None:
                            iter_completion = hit
                            runner.terminate()
                            break
            finally:
                wd.stop()

            if iter_session_id is not None and captures:
                try:
                    iter_session_file = capture_session(
                        session_id=iter_session_id,
                        sandbox_cwd=handle.worktree_path,
                        host_repo_path=setup.cwd,
                        branch=wt.branch,
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

    finally:
        if handle is not None:
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
        if handle is not None:
            try:
                handle.close()
            except Exception:
                pass
        if sink is not None:
            sink.close()
        close_result = wt.close()
        if close_result.action == "preserved":
            preserved = wt.worktree_path

    last = iterations[-1] if iterations else None
    return assemble(
        iterations=iterations,
        completion_signal=completion_hit,
        branch=wt.branch,
        stdout="".join(stdout_chunks),
        worktree_path=wt.worktree_path,
        preserved_worktree_path=preserved,
        cwd=setup.cwd,
        prompt=rendered_prompt,
        env=setup.merged_env,
        log_file_path=log_path,
        session_id=last.session_id if last else None,
        session_file_path=last.session_file_path if last else None,
        usage=last.usage if last else None,
    )


__all__ = ["_run_loop"]
