"""Verify `eden cost` real implementation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from eden.cli.main import app

pytestmark = pytest.mark.unit


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _write_session(
    repo: Path,
    *,
    branch: str,
    iteration: int,
    session_id: str,
    input_tokens: int = 100,
    output_tokens: int = 50,
    cache_creation_input_tokens: int = 10,
    cache_read_input_tokens: int = 5,
) -> Path:
    """Write a minimal stream-json session JSONL under .eden/sessions/."""
    path = repo / ".eden" / "sessions" / branch / f"iter-{iteration}-{session_id}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(
            {
                "type": "result",
                "session_id": session_id,
                "usage": {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cache_creation_input_tokens": cache_creation_input_tokens,
                    "cache_read_input_tokens": cache_read_input_tokens,
                },
            }
        ),
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_cost_no_sessions_dir(runner: CliRunner, tmp_path: Path) -> None:
    result = runner.invoke(app, ["cost", "--cwd", str(tmp_path)])
    assert result.exit_code == 0
    combined = (result.output or "") + (result.stderr or "")
    assert "no .eden/sessions/" in combined.lower()


def test_cost_aggregates_per_branch(runner: CliRunner, tmp_path: Path) -> None:
    _write_session(tmp_path, branch="feat-a", iteration=0, session_id="sess-1", input_tokens=200)
    _write_session(tmp_path, branch="feat-a", iteration=1, session_id="sess-2", input_tokens=300)
    _write_session(tmp_path, branch="feat-b", iteration=0, session_id="sess-3", input_tokens=400)

    result = runner.invoke(app, ["cost", "--cwd", str(tmp_path)])
    assert result.exit_code == 0, result.output
    # Two branches + a TOTAL row visible in the table.
    assert "feat-a" in result.output
    assert "feat-b" in result.output
    assert "TOTAL" in result.output


def test_cost_filter_by_branch(runner: CliRunner, tmp_path: Path) -> None:
    _write_session(tmp_path, branch="feat-a", iteration=0, session_id="s1")
    _write_session(tmp_path, branch="feat-b", iteration=0, session_id="s2")

    result = runner.invoke(app, ["cost", "--cwd", str(tmp_path), "--branch", "feat-a"])
    assert result.exit_code == 0, result.output
    assert "feat-a" in result.output
    assert "feat-b" not in result.output


def test_cost_skips_sessions_with_no_result_line(runner: CliRunner, tmp_path: Path) -> None:
    """A session JSONL without a `result` line must not crash, just be skipped."""
    path = tmp_path / ".eden" / "sessions" / "x" / "iter-0-s.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({"type": "user", "message": {"content": "hi"}}) + "\n", encoding="utf-8"
    )

    result = runner.invoke(app, ["cost", "--cwd", str(tmp_path)])
    assert result.exit_code == 0
    combined = (result.output or "") + (result.stderr or "")
    # No usage was found, so we either fall through to "no usage" or report
    # nothing — either way exit cleanly.
    assert "no usage" in combined.lower() or "TOTAL" not in combined
