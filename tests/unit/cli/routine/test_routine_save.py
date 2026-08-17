"""Verify `eden routine save` real implementation."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from eden.cli.main import app
from eden.cli.routine._store import load_routine

pytestmark = pytest.mark.unit


def test_save_persists_resolved_default_model(runner: CliRunner, repo_dir: Path) -> None:
    result = runner.invoke(
        app,
        ["routine", "save", "nightly", "--sandbox", "no-sandbox", "--cwd", str(repo_dir)],
    )
    assert result.exit_code == 0, result.output
    config = load_routine(repo_dir, "nightly")
    assert config.agent == "claude-code"
    assert config.model == "claude-opus-4-8"
    assert config.sandbox == "no-sandbox"
    assert config.template == "simple-loop"
    assert config.backlog == "github"


def test_save_refuses_overwrite_without_force(runner: CliRunner, repo_dir: Path) -> None:
    args = ["routine", "save", "nightly", "--sandbox", "no-sandbox", "--cwd", str(repo_dir)]
    assert runner.invoke(app, args).exit_code == 0
    result = runner.invoke(app, args)
    assert result.exit_code != 0
    combined = (result.output or "") + (result.stderr or "")
    assert "already exists" in combined.lower()


def test_save_force_overwrites(runner: CliRunner, repo_dir: Path) -> None:
    base = ["routine", "save", "nightly", "--cwd", str(repo_dir)]
    runner.invoke(app, [*base, "--sandbox", "no-sandbox"])
    result = runner.invoke(app, [*base, "--sandbox", "docker", "--image-name", "eden:x", "--force"])
    assert result.exit_code == 0, result.output
    config = load_routine(repo_dir, "nightly")
    assert config.sandbox == "docker"
    assert config.image_name == "eden:x"


def test_save_rejects_unknown_agent(runner: CliRunner, repo_dir: Path) -> None:
    result = runner.invoke(
        app,
        ["routine", "save", "nightly", "--agent", "bogus", "--cwd", str(repo_dir)],
    )
    assert result.exit_code != 0
    with pytest.raises(FileNotFoundError):
        load_routine(repo_dir, "nightly")


def test_save_requires_image_name_for_docker(runner: CliRunner, repo_dir: Path) -> None:
    result = runner.invoke(
        app,
        ["routine", "save", "nightly", "--sandbox", "docker", "--cwd", str(repo_dir)],
    )
    assert result.exit_code != 0
    combined = (result.output or "") + (result.stderr or "")
    assert "image-name" in combined.lower()


def test_save_rejects_unsafe_name(runner: CliRunner, repo_dir: Path) -> None:
    result = runner.invoke(
        app,
        ["routine", "save", "../escape", "--sandbox", "no-sandbox", "--cwd", str(repo_dir)],
    )
    assert result.exit_code != 0
