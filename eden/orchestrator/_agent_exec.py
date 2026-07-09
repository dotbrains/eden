"""Agent subprocess execution for one orchestrator iteration."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import cast

from eden._types import Usage
from eden.abort import AbortSignal
from eden.agents._context import IterationContext
from eden.agents._protocol import Agent
from eden.orchestrator._completion import match
from eden.orchestrator._idle import IdleWatchdog
from eden.orchestrator._logging import LoopLogger
from eden.orchestrator._runner import _AgentRunner
from eden.providers._protocols import SandboxHandle
from eden.streaming import StreamEvent
from eden.streaming._bounded_tail import BoundedTail
from eden.tracing import span


@dataclass(frozen=True)
class AgentExecution:
    completion: str | None
    exit_code: int | None
    stderr: str
    session_id: str | None
    usage: Usage | None


def execute_agent_iteration(
    *,
    agent: Agent,
    argv: list[str],
    env: Mapping[str, str],
    handle: SandboxHandle,
    worktree_path: Path,
    branch: str,
    name: str | None,
    resume_session: str | None,
    rendered_prompt: str,
    iteration: int,
    idle_timeout: float,
    idle_warning_interval: float | None,
    completion_signal: str | list[str],
    completion_timeout: float | None,
    logger: LoopLogger,
    on_event: Callable[[StreamEvent], None] | None,
    signal: AbortSignal,
    stdout_chunks: BoundedTail,
    timestamp: Callable[[], datetime],
) -> AgentExecution:
    wd = IdleWatchdog(
        idle_timeout=idle_timeout,
        idle_warning_interval=idle_warning_interval,
    )
    wd.start()
    try:
        iter_completion: str | None = None
        iter_session_id: str | None = None
        iter_usage: Usage | None = None
        agent_exit_code: int | None = None
        agent_stderr = ""
        agent_cwd = handle.worktree_path if handle.worktree_path.exists() else None
        stdin_payload = _stdin_payload(
            agent=agent,
            iteration=iteration,
            rendered_prompt=rendered_prompt,
            handle=handle,
            worktree_path=worktree_path,
            branch=branch,
            name=name,
            resume_session=resume_session,
        )

        with (
            span(
                "eden.agent.exec",
                attributes={
                    "agent.name": agent.name,
                    "agent.model": getattr(agent, "model", None),
                    "iteration.index": iteration,
                    "branch": branch,
                },
            ),
            _AgentRunner(
                argv=argv,
                env=env,
                watchdog=wd,
                cwd=agent_cwd,
                stdin=stdin_payload,
            ) as runner,
        ):

            def _emit_warning(minutes: int) -> None:
                logger.emit_idle_warning(
                    agent_name=agent.name,
                    iteration=iteration,
                    timestamp=timestamp(),
                    minutes_idle=minutes,
                    on_event=on_event,
                )

            def _emit_raw(raw_line: str) -> None:
                logger.emit_raw(
                    agent_name=agent.name,
                    iteration=iteration,
                    timestamp=timestamp(),
                    text=raw_line,
                )

            def _handle_event(ev: StreamEvent) -> None:
                nonlocal iter_session_id, iter_usage
                if ev.type == "usage":
                    iter_session_id = ev.session_id
                    iter_usage = ev.usage
                elif ev.type == "session_id":
                    iter_session_id = ev.session_id
                logger.write(ev)
                if on_event is not None:
                    on_event(ev)
                logger.forward_agent_event(ev)

            for line in runner.iter_lines(signal=signal, on_warning=_emit_warning):
                stdout_chunks.push(line + "\n")
                _emit_raw(line)
                ev = _parse_event(agent=agent, line=line, iteration=iteration, timestamp=timestamp)
                _handle_event(ev)
                hit = match(line, completion_signal)
                if hit is not None:
                    iter_completion = hit
                    drain = runner.drain_remaining(total_timeout=completion_timeout)
                    if drain.timed_out:
                        warn_ev = StreamEvent(
                            type="text",
                            agent_name=agent.name,
                            iteration=iteration,
                            timestamp=timestamp(),
                            text=(
                                f"[eden] completion_timeout ({completion_timeout}s) "
                                "elapsed after completion signal — agent process did "
                                "not EOF; terminating now. Iteration succeeded."
                            ),
                        )
                        logger.write(warn_ev)
                        if on_event is not None:
                            on_event(warn_ev)
                    for trailing in drain.lines:
                        stdout_chunks.push(trailing + "\n")
                        _emit_raw(trailing)
                        trailing_parsed = agent.parse_stream(trailing)
                        if trailing_parsed is not None:
                            _handle_event(
                                replace(
                                    trailing_parsed,
                                    iteration=iteration,
                                    agent_name=agent.name,
                                )
                            )
                    runner.terminate()
                    break
            agent_exit_code = runner.exit_code()
            agent_stderr = runner.stderr_text
        return AgentExecution(
            completion=iter_completion,
            exit_code=agent_exit_code,
            stderr=agent_stderr,
            session_id=iter_session_id,
            usage=iter_usage,
        )
    finally:
        wd.stop()


def _stdin_payload(
    *,
    agent: Agent,
    iteration: int,
    rendered_prompt: str,
    handle: SandboxHandle,
    worktree_path: Path,
    branch: str,
    name: str | None,
    resume_session: str | None,
) -> str | None:
    stdin_fn = getattr(agent, "stdin_content", None)
    if not callable(stdin_fn):
        return None
    return cast(
        str | None,
        stdin_fn(
            IterationContext(
                iteration=iteration,
                prompt=rendered_prompt,
                sandbox_handle=handle,
                worktree_path=worktree_path,
                branch=branch,
                name=name,
                resume_session=resume_session,
            )
        ),
    )


def _parse_event(
    *,
    agent: Agent,
    line: str,
    iteration: int,
    timestamp: Callable[[], datetime],
) -> StreamEvent:
    parsed = agent.parse_stream(line)
    if parsed is not None:
        return replace(parsed, iteration=iteration, agent_name=agent.name)
    return StreamEvent(
        type="text",
        agent_name=agent.name,
        iteration=iteration,
        timestamp=timestamp(),
        text=line,
    )


__all__ = ["AgentExecution", "execute_agent_iteration"]
