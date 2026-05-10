"""Verify ``format_agent_error_recovery`` formats a copy-pastable hint."""

from __future__ import annotations

from pathlib import Path

import pytest

from eden.errors import AgentError
from eden.orchestrator._recovery import format_agent_error_recovery

pytestmark = pytest.mark.unit


def _err(
    *,
    parsed: str | None = None,
    stderr: str = "",
    exit_code: int = 1,
    agent_name: str = "codex",
) -> AgentError:
    return AgentError(
        message="agent failed",
        agent_name=agent_name,
        exit_code=exit_code,
        stderr=stderr,
        parsed_error=parsed,
    )


def test_includes_parsed_error_body() -> None:
    out = format_agent_error_recovery(
        error=_err(parsed="rate limit hit"),
        branch="feat/x",
        worktree_path=Path("/tmp/eden/wt"),
        log_path=Path("/tmp/eden/run.log"),
    )
    assert "rate limit hit" in out
    assert "feat/x" in out
    assert "/tmp/eden/wt" in out
    assert "/tmp/eden/run.log" in out


def test_falls_back_to_stderr_when_parsed_missing() -> None:
    out = format_agent_error_recovery(
        error=_err(stderr="connection refused\n"),
        branch="feat/x",
        worktree_path=Path("/tmp/wt"),
        log_path=None,
    )
    assert "connection refused" in out


def test_handles_no_output_at_all() -> None:
    """Both parsed and stderr empty → user still gets a useful message."""
    out = format_agent_error_recovery(
        error=_err(),
        branch="b",
        worktree_path=Path("/tmp/wt"),
        log_path=None,
    )
    assert "(no agent output captured)" in out


def test_omits_log_line_when_no_log_path() -> None:
    out = format_agent_error_recovery(
        error=_err(parsed="boom"),
        branch="b",
        worktree_path=Path("/tmp/wt"),
        log_path=None,
    )
    assert "log:" not in out
    assert "less " not in out  # no `less <path>` next-step suggestion either


def test_includes_next_steps_block() -> None:
    out = format_agent_error_recovery(
        error=_err(parsed="boom"),
        branch="feat/x",
        worktree_path=Path("/tmp/wt"),
        log_path=Path("/tmp/run.log"),
    )
    assert "Next steps:" in out
    assert "cd /tmp/wt" in out
    assert "git diff feat/x" in out
    assert "eden clean" in out


def test_includes_agent_name_and_exit_code() -> None:
    out = format_agent_error_recovery(
        error=_err(parsed="boom", agent_name="pi", exit_code=7),
        branch="b",
        worktree_path=Path("/wt"),
        log_path=None,
    )
    assert "pi" in out
    assert "7" in out
