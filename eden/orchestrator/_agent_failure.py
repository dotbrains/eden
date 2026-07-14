"""Agent failure handling for orchestrator iterations."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Protocol

from eden.agents._errors import parse_stdout_error
from eden.errors import AgentError
from eden.orchestrator._agent_exec import AgentExecution
from eden.orchestrator._recovery import format_agent_error_recovery
from eden.streaming import StreamEvent


class _EventSink(Protocol):
    def write(self, event: StreamEvent) -> None: ...


def raise_agent_exit_without_completion(
    *,
    agent_name: str,
    iteration: int,
    exit_code: int,
    stderr: str,
    stdout: str,
    branch: str,
    worktree_path: Path,
    log_path: Path | None,
    sink: _EventSink | None,
    on_event: Callable[[StreamEvent], None] | None,
    timestamp: Callable[[], datetime],
) -> None:
    parsed_stdout = parse_stdout_error(stdout)
    stderr_text = stderr.strip()
    body = parsed_stdout or stderr_text or "(no output)"
    err = AgentError(
        message=(
            f"agent {agent_name!r} exited with code {exit_code} "
            f"on iteration {iteration} without a completion signal: {body}"
        ),
        hint=(
            "check the agent's stdout/stderr in the run log; for "
            "claude-code, ensure the prompt requests a "
            "<promise>COMPLETE</promise> tag"
        ),
        agent_name=agent_name,
        exit_code=exit_code,
        stderr=stderr_text,
        parsed_error=parsed_stdout,
    )
    recovery_text = format_agent_error_recovery(
        error=err,
        branch=branch,
        worktree_path=worktree_path,
        log_path=log_path,
    )
    recovery_ev = StreamEvent(
        type="text",
        agent_name=agent_name,
        iteration=iteration,
        timestamp=timestamp(),
        text=recovery_text,
    )
    if sink is not None:
        sink.write(recovery_ev)
    if on_event is not None:
        on_event(recovery_ev)
    raise err


def raise_if_agent_failed_without_completion(
    *,
    agent_name: str,
    iteration: int,
    execution: AgentExecution,
    stdout: str,
    branch: str,
    worktree_path: Path,
    log_path: Path | None,
    sink: _EventSink | None,
    on_event: Callable[[StreamEvent], None] | None,
    timestamp: Callable[[], datetime],
) -> None:
    exit_code = execution.exit_code
    if execution.completion is not None or exit_code is None or exit_code == 0:
        return
    raise_agent_exit_without_completion(
        agent_name=agent_name,
        iteration=iteration,
        exit_code=exit_code,
        stderr=execution.stderr,
        stdout=stdout,
        branch=branch,
        worktree_path=worktree_path,
        log_path=log_path,
        sink=sink,
        on_event=on_event,
        timestamp=timestamp,
    )


__all__ = ["raise_agent_exit_without_completion", "raise_if_agent_failed_without_completion"]
