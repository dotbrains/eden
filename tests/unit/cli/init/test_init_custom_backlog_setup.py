"""Verify custom backlog setup notes in eden init scaffolds."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from eden.cli.main import app

pytestmark = pytest.mark.unit
pytest_plugins = ["tests.unit.cli.cli_init_fixtures"]


def test_init_custom_backlog_writes_setup_notes(runner: CliRunner, repo_dir: Path) -> None:
    result = runner.invoke(
        app,
        ["init", "--yes", "--template", "simple-loop", "--backlog", "custom"],
    )

    assert result.exit_code == 0, result.output
    setup = (repo_dir / ".eden" / "SETUP_BACKLOG.md").read_text(encoding="utf-8")
    assert "`--backlog custom`" in setup
    assert "list, view, and close" in setup
    assert "eden docker build-image" in setup


def test_init_github_backlog_omits_setup_notes(runner: CliRunner, repo_dir: Path) -> None:
    result = runner.invoke(
        app,
        ["init", "--yes", "--template", "simple-loop", "--backlog", "github"],
    )

    assert result.exit_code == 0, result.output
    assert not (repo_dir / ".eden" / "SETUP_BACKLOG.md").exists()


def test_init_custom_backlog_uses_selected_sandbox_command(
    runner: CliRunner, repo_dir: Path
) -> None:
    result = runner.invoke(
        app,
        [
            "init",
            "--yes",
            "--template",
            "simple-loop",
            "--backlog",
            "custom",
            "--sandbox",
            "podman",
        ],
    )

    assert result.exit_code == 0, result.output
    setup = (repo_dir / ".eden" / "SETUP_BACKLOG.md").read_text(encoding="utf-8")
    assert "eden podman build-image" in setup
