"""Verify `eden replay` real implementation."""

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


def _seed(repo: Path, *, branch: str, iteration: int, session_id: str) -> Path:
    """Write a minimal stream-json session JSONL with system/user/assistant/result entries."""
    path = repo / ".eden" / "sessions" / branch / f"iter-{iteration}-{session_id}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps({"type": "system", "subtype": "init", "model": "claude-opus-4-7"}),
        json.dumps({"type": "user", "message": {"content": "fix the failing test"}}),
        json.dumps(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "text", "text": "Looking at the test now."},
                        {"type": "tool_use", "name": "Read", "input": {"file_path": "/x.py"}},
                    ]
                },
            }
        ),
        json.dumps(
            {
                "type": "result",
                "session_id": session_id,
                "usage": {
                    "input_tokens": 100,
                    "output_tokens": 50,
                    "cache_creation_input_tokens": 0,
                    "cache_read_input_tokens": 0,
                },
            }
        ),
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_replay_by_explicit_path(runner: CliRunner, tmp_path: Path) -> None:
    path = _seed(tmp_path, branch="b", iteration=0, session_id="s1")
    result = runner.invoke(app, ["replay", str(path)])
    assert result.exit_code == 0, result.output
    assert "fix the failing test" in result.output
    assert "Looking at the test" in result.output
    # Tool use rendered (default --tools).
    assert "Read" in result.output
    # Final usage line appears.
    assert "input=100" in result.output


def test_replay_by_branch_iter_shorthand(runner: CliRunner, tmp_path: Path) -> None:
    _seed(tmp_path, branch="featx", iteration=2, session_id="s2")
    result = runner.invoke(app, ["replay", "featx/2", "--cwd", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "fix the failing test" in result.output


def test_replay_by_session_id(runner: CliRunner, tmp_path: Path) -> None:
    _seed(tmp_path, branch="b", iteration=0, session_id="abc-123")
    result = runner.invoke(app, ["replay", "abc-123", "--cwd", str(tmp_path)])
    assert result.exit_code == 0, result.output


def test_replay_unknown_target(runner: CliRunner, tmp_path: Path) -> None:
    (tmp_path / ".eden" / "sessions").mkdir(parents=True)
    result = runner.invoke(app, ["replay", "nope", "--cwd", str(tmp_path)])
    assert result.exit_code != 0
    combined = (result.output or "") + (result.stderr or "")
    assert "no session matches" in combined.lower()


def test_replay_no_tools_flag_hides_tool_uses(runner: CliRunner, tmp_path: Path) -> None:
    _seed(tmp_path, branch="b", iteration=0, session_id="s1")
    result = runner.invoke(app, ["replay", "s1", "--cwd", str(tmp_path), "--no-tools"])
    assert result.exit_code == 0
    assert "Looking at the test" in result.output
    # Tool name should not appear when --no-tools is set.
    assert "→ Read" not in result.output
