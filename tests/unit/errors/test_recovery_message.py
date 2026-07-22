"""Verify ``format_agent_error_recovery`` formats a copy-pastable hint."""

from __future__ import annotations

import shlex
from pathlib import Path

import pytest

from eden.errors import AgentError
from eden.orchestrator._recovery import format_agent_error_recovery

pytestmark = pytest.mark.unit


def _err(
    *,
    parsed: str | None = None,
    stderr: str = "",
    stdout: str = "",
    exit_code: int = 1,
    agent_name: str = "codex",
) -> AgentError:
    return AgentError(
        message="agent failed",
        agent_name=agent_name,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        parsed_error=parsed,
    )


def test_includes_parsed_error_body(tmp_path: Path) -> None:
    wt = tmp_path / "wt"
    log = tmp_path / "run.log"
    out = format_agent_error_recovery(
        error=_err(parsed="rate limit hit"),
        branch="feat/x",
        worktree_path=wt,
        log_path=log,
    )
    assert "rate limit hit" in out
    assert "feat/x" in out
    # Use ``str(path)`` so the assertion matches the OS-native path
    # representation (Windows: backslashes; POSIX: forward slashes).
    assert str(wt) in out
    assert str(log) in out


def test_falls_back_to_stderr_when_parsed_missing(tmp_path: Path) -> None:
    out = format_agent_error_recovery(
        error=_err(stderr="connection refused\n"),
        branch="feat/x",
        worktree_path=tmp_path / "wt",
        log_path=None,
    )
    assert "connection refused" in out


def test_handles_no_output_at_all(tmp_path: Path) -> None:
    """Both parsed and stderr empty → user still gets a useful message."""
    out = format_agent_error_recovery(
        error=_err(),
        branch="b",
        worktree_path=tmp_path / "wt",
        log_path=None,
    )
    assert "(no agent output captured)" in out


def test_falls_back_to_stdout_when_stderr_missing(tmp_path: Path) -> None:
    out = format_agent_error_recovery(
        error=_err(stdout="ordinary stdout failure\n"),
        branch="b",
        worktree_path=tmp_path / "wt",
        log_path=None,
    )
    assert "ordinary stdout failure" in out


def test_omits_log_line_when_no_log_path(tmp_path: Path) -> None:
    out = format_agent_error_recovery(
        error=_err(parsed="boom"),
        branch="b",
        worktree_path=tmp_path / "wt",
        log_path=None,
    )
    assert "log:" not in out
    assert "less " not in out  # no `less <path>` next-step suggestion either


def test_includes_next_steps_block(tmp_path: Path) -> None:
    wt = tmp_path / "wt"
    log = tmp_path / "run.log"
    out = format_agent_error_recovery(
        error=_err(parsed="boom"),
        branch="feat/x",
        worktree_path=wt,
        log_path=log,
    )
    assert "Next steps:" in out
    # Shell-quoted commands so paths with spaces don't break the paste.
    assert f"cd {shlex.quote(str(wt))}" in out
    assert f"less {shlex.quote(str(log))}" in out
    assert "git diff feat/x" in out
    assert "eden clean" in out


def test_quotes_path_with_spaces(tmp_path: Path) -> None:
    """A worktree path containing spaces is shell-quoted in the cd command."""
    wt = tmp_path / "Foo Bar" / "worktree"
    out = format_agent_error_recovery(
        error=_err(parsed="boom"),
        branch="feat/x",
        worktree_path=wt,
        log_path=None,
    )
    # Sanity-check the test setup actually exercises the spaces case.
    assert " " in str(wt)
    # ``shlex.quote`` wraps the platform-native path repr.
    assert f"cd {shlex.quote(str(wt))}" in out


def test_quotes_branch_with_special_chars(tmp_path: Path) -> None:
    """A branch name with shell metacharacters is quoted in ``git diff``."""
    out = format_agent_error_recovery(
        error=_err(parsed="boom"),
        branch="feat/x;rm -rf /",
        worktree_path=tmp_path / "wt",
        log_path=None,
    )
    assert "git diff 'feat/x;rm -rf /'" in out


def test_includes_agent_name_and_exit_code(tmp_path: Path) -> None:
    out = format_agent_error_recovery(
        error=_err(parsed="boom", agent_name="pi", exit_code=7),
        branch="b",
        worktree_path=tmp_path / "wt",
        log_path=None,
    )
    assert "pi" in out
    assert "7" in out
