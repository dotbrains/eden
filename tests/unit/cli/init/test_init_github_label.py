"""Verify `eden init --create-label`."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from eden.cli.main import app

pytestmark = pytest.mark.unit
pytest_plugins = ["tests.unit.cli.cli_init_fixtures"]


def test_init_create_label_runs_gh_for_github_backlog(runner: CliRunner, repo_dir: Path) -> None:
    completed: subprocess.CompletedProcess[bytes] = subprocess.CompletedProcess(
        args=[], returncode=0
    )
    with patch("eden.cli._init_github.subprocess.run", return_value=completed) as run_mock:
        result = runner.invoke(
            app,
            [
                "init",
                "--yes",
                "--template",
                "simple-loop",
                "--backlog",
                "github",
                "--create-label",
            ],
        )
    assert result.exit_code == 0, result.output
    assert (repo_dir / ".eden").is_dir()
    argv = run_mock.call_args[0][0]
    assert argv[:4] == ["gh", "label", "create", "eden"]
    assert "--force" in argv


def test_init_create_label_rejects_non_github_backlog(runner: CliRunner, repo_dir: Path) -> None:
    with patch("eden.cli._init_github.subprocess.run") as run_mock:
        result = runner.invoke(
            app,
            [
                "init",
                "--yes",
                "--template",
                "simple-loop",
                "--backlog",
                "beads",
                "--create-label",
            ],
        )
    assert result.exit_code != 0
    assert not (repo_dir / ".eden").exists()
    run_mock.assert_not_called()
