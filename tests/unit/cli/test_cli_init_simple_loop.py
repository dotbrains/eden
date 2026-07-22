"""Verify eden init simple-loop template integration."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from eden.cli.main import app

pytestmark = pytest.mark.unit
pytest_plugins = ["tests.unit.cli.cli_init_fixtures"]


def test_init_simple_loop_template_writes_files(runner: CliRunner, repo_dir: Path) -> None:
    result = runner.invoke(
        app,
        ["init", "--yes", "--template", "simple-loop", "--backlog", "github"],
    )
    assert result.exit_code == 0, result.output
    eden_dir = repo_dir / ".eden"
    expected = {"Dockerfile", "prompt.md", "main.py", ".env.example", ".gitignore"}
    assert {p.name for p in eden_dir.iterdir()} == expected


def test_init_simple_loop_github_threads_gh_commands(runner: CliRunner, repo_dir: Path) -> None:
    runner.invoke(
        app,
        ["init", "--yes", "--template", "simple-loop", "--backlog", "github"],
    )
    prompt = (repo_dir / ".eden" / "prompt.md").read_text(encoding="utf-8")
    assert "gh issue list" in prompt
    assert "gh issue view <ID>" in prompt
    assert "gh issue close <ID>" in prompt


def test_init_simple_loop_beads_threads_bd_commands(runner: CliRunner, repo_dir: Path) -> None:
    runner.invoke(
        app,
        ["init", "--yes", "--template", "simple-loop", "--backlog", "beads"],
    )
    prompt = (repo_dir / ".eden" / "prompt.md").read_text(encoding="utf-8")
    assert "bd ready --json" in prompt
    assert "bd show <ID>" in prompt
    assert "bd close <ID>" in prompt


def test_init_simple_loop_dockerfile_includes_backlog_install(
    runner: CliRunner, repo_dir: Path
) -> None:
    runner.invoke(
        app,
        ["init", "--yes", "--template", "simple-loop", "--backlog", "github"],
    )
    dockerfile = (repo_dir / ".eden" / "Dockerfile").read_text(encoding="utf-8")
    assert "gh" in dockerfile  # gh CLI install line present
    assert "ARG AGENT_UID=1000" in dockerfile
    assert "groupadd --gid ${AGENT_GID} --non-unique agent" in dockerfile
    assert "useradd --uid ${AGENT_UID} --non-unique --gid ${AGENT_GID}" in dockerfile
    assert "USER ${AGENT_UID}:${AGENT_GID}" in dockerfile


def test_init_simple_loop_invalid_backlog_rejected(runner: CliRunner, repo_dir: Path) -> None:
    result = runner.invoke(
        app,
        ["init", "--yes", "--template", "simple-loop", "--backlog", "trello"],
    )
    assert result.exit_code != 0


def test_init_simple_loop_default_backlog_is_github(runner: CliRunner, repo_dir: Path) -> None:
    """Without --backlog, --yes mode falls back to github."""
    result = runner.invoke(
        app,
        ["init", "--yes", "--template", "simple-loop"],
    )
    assert result.exit_code == 0, result.output
    prompt = (repo_dir / ".eden" / "prompt.md").read_text(encoding="utf-8")
    assert "gh issue list" in prompt


def test_init_simple_loop_linear_threads_helpers(runner: CliRunner, repo_dir: Path) -> None:
    result = runner.invoke(
        app,
        ["init", "--yes", "--template", "simple-loop", "--backlog", "linear"],
    )
    assert result.exit_code == 0, result.output
    prompt = (repo_dir / ".eden" / "prompt.md").read_text(encoding="utf-8")
    assert "linear-list" in prompt
    dockerfile = (repo_dir / ".eden" / "Dockerfile").read_text(encoding="utf-8")
    assert "linear-list" in dockerfile  # helper script baked into image
    env_ex = (repo_dir / ".eden" / ".env.example").read_text(encoding="utf-8")
    assert "LINEAR_API_KEY" in env_ex


def test_init_simple_loop_jira_threads_jira_cli(runner: CliRunner, repo_dir: Path) -> None:
    result = runner.invoke(
        app,
        ["init", "--yes", "--template", "simple-loop", "--backlog", "jira"],
    )
    assert result.exit_code == 0, result.output
    prompt = (repo_dir / ".eden" / "prompt.md").read_text(encoding="utf-8")
    assert "jira issue list" in prompt
    dockerfile = (repo_dir / ".eden" / "Dockerfile").read_text(encoding="utf-8")
    assert "jira-cli" in dockerfile
    env_ex = (repo_dir / ".eden" / ".env.example").read_text(encoding="utf-8")
    assert "JIRA_API_TOKEN" in env_ex
