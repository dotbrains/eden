"""Verify `eden routine list` / `show` / `remove` real implementation."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from eden.cli.main import app
from eden.cli.routine._store import RoutineConfig, list_routines, save_routine

pytestmark = pytest.mark.unit


def _save(repo: Path, name: str, **overrides: object) -> None:
    defaults: dict[str, object] = {
        "sandbox": "no-sandbox",
        "agent": "claude-code",
        "model": "claude-opus-4-8",
        "template": "simple-loop",
        "backlog": "github",
        "image_name": None,
        "max_iterations": 3,
        "idle_timeout": 600.0,
        "completion_timeout": 60.0,
    }
    defaults.update(overrides)
    save_routine(repo, name, RoutineConfig(**defaults))  # type: ignore[arg-type]


def test_list_reports_no_routines(runner: CliRunner, repo_dir: Path) -> None:
    result = runner.invoke(app, ["routine", "list", "--cwd", str(repo_dir)])
    assert result.exit_code == 0
    combined = (result.output or "") + (result.stderr or "")
    assert "no routines" in combined.lower()


def test_list_shows_saved_routines(runner: CliRunner, repo_dir: Path) -> None:
    _save(repo_dir, "nightly")
    result = runner.invoke(app, ["routine", "list", "--cwd", str(repo_dir)])
    assert result.exit_code == 0, result.output
    combined = (result.output or "") + (result.stderr or "")
    assert "nightly" in combined
    assert "claude-code" in combined


def test_show_prints_full_config(runner: CliRunner, repo_dir: Path) -> None:
    _save(repo_dir, "nightly", max_iterations=9)
    result = runner.invoke(app, ["routine", "show", "nightly", "--cwd", str(repo_dir)])
    assert result.exit_code == 0, result.output
    assert "max_iterations: 9" in result.output


def test_show_missing_routine_fails(runner: CliRunner, repo_dir: Path) -> None:
    result = runner.invoke(app, ["routine", "show", "missing", "--cwd", str(repo_dir)])
    assert result.exit_code != 0


def test_remove_deletes_routine(runner: CliRunner, repo_dir: Path) -> None:
    _save(repo_dir, "nightly")
    result = runner.invoke(app, ["routine", "remove", "nightly", "--cwd", str(repo_dir)])
    assert result.exit_code == 0, result.output
    assert list_routines(repo_dir) == []


def test_remove_missing_routine_fails(runner: CliRunner, repo_dir: Path) -> None:
    result = runner.invoke(app, ["routine", "remove", "missing", "--cwd", str(repo_dir)])
    assert result.exit_code != 0
