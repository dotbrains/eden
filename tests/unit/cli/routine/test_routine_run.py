"""Verify `eden routine run` real implementation.

Mirrors ``tests/unit/cli/test_cli_run.py``: stub ``eden.run`` and assert the
saved routine's config is forwarded correctly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

import eden
from eden.cli.main import app
from eden.cli.routine._store import RoutineConfig, save_routine

pytestmark = pytest.mark.unit


@pytest.fixture
def fake_run(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    fake_result = MagicMock()
    fake_result.completion_signal = "<promise>COMPLETE</promise>"
    fake_result.iterations = [MagicMock()]
    fake_result.branch = "eden/nightly"
    mock = MagicMock(return_value=fake_result)
    monkeypatch.setattr("eden.cli.routine._run.eden_run", mock)
    return mock


def _kwargs(call: Any) -> dict[str, Any]:
    return dict(call.kwargs)


def test_run_forwards_saved_config(runner: CliRunner, repo_dir: Path, fake_run: MagicMock) -> None:
    save_routine(
        repo_dir,
        "nightly",
        RoutineConfig(
            sandbox="no-sandbox",
            agent="claude-code",
            model="claude-opus-4-8",
            template="simple-loop",
            backlog="github",
            image_name=None,
            max_iterations=5,
            idle_timeout=120.0,
            completion_timeout=30.0,
        ),
    )
    result = runner.invoke(app, ["routine", "run", "nightly", "--cwd", str(repo_dir)])
    assert result.exit_code == 0, result.output
    assert fake_run.call_count == 1
    kw = _kwargs(fake_run.call_args)
    assert isinstance(kw["agent"], eden.Agent)
    assert kw["max_iterations"] == 5
    assert kw["idle_timeout"] == 120.0
    assert kw["completion_timeout"] == 30.0
    assert "gh issue list" in kw["prompt"]


def test_run_missing_routine_fails_without_calling_eden_run(
    runner: CliRunner, repo_dir: Path, fake_run: MagicMock
) -> None:
    result = runner.invoke(app, ["routine", "run", "missing", "--cwd", str(repo_dir)])
    assert result.exit_code != 0
    fake_run.assert_not_called()


def test_run_rejects_hand_edited_invalid_backlog(
    runner: CliRunner, repo_dir: Path, fake_run: MagicMock
) -> None:
    save_routine(
        repo_dir,
        "nightly",
        RoutineConfig(
            sandbox="no-sandbox",
            agent="claude-code",
            model="claude-opus-4-8",
            template="simple-loop",
            backlog="bogus",
            image_name=None,
            max_iterations=3,
            idle_timeout=600.0,
            completion_timeout=60.0,
        ),
    )
    result = runner.invoke(app, ["routine", "run", "nightly", "--cwd", str(repo_dir)])
    assert result.exit_code != 0
    fake_run.assert_not_called()


def test_run_rejects_hand_edited_invalid_template(
    runner: CliRunner, repo_dir: Path, fake_run: MagicMock
) -> None:
    save_routine(
        repo_dir,
        "nightly",
        RoutineConfig(
            sandbox="no-sandbox",
            agent="claude-code",
            model="claude-opus-4-8",
            template="bogus",
            backlog="github",
            image_name=None,
            max_iterations=3,
            idle_timeout=600.0,
            completion_timeout=60.0,
        ),
    )
    result = runner.invoke(app, ["routine", "run", "nightly", "--cwd", str(repo_dir)])
    assert result.exit_code != 0
    fake_run.assert_not_called()
