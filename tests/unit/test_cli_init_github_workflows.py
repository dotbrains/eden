"""Verify ``eden init --template github-agent-workflows`` integration."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from eden.cli.main import app

pytestmark = pytest.mark.unit
pytest_plugins = ["tests.unit.cli_init_fixtures"]


def test_init_github_agent_workflows_writes_workflows_and_factory(
    runner: CliRunner,
    repo_dir: Path,
) -> None:
    result = runner.invoke(
        app,
        ["init", "--yes", "--template", "github-agent-workflows", "--backlog", "github"],
    )
    assert result.exit_code == 0, result.output

    implement = repo_dir / ".github" / "workflows" / "eden-agent-implement.yml"
    review = repo_dir / ".github" / "workflows" / "eden-agent-review.yml"
    factory = repo_dir / ".eden" / "github" / "factory.py"
    assert implement.is_file()
    assert review.is_file()
    assert factory.is_file()

    implement_text = implement.read_text(encoding="utf-8")
    assert "agent:implement" in implement_text
    assert "Detect issue shape" in implement_text
    assert "Preflight existing PR" in implement_text
    assert "gh pr create --draft" in implement_text

    review_text = review.read_text(encoding="utf-8")
    assert "agent:review" in review_text
    assert "Post PR review" in review_text
    assert "Post thread replies" in review_text

    assert "ThreadPoolExecutor" in factory.read_text(encoding="utf-8")


def test_init_github_agent_workflows_custom_backlog_scaffolds_setup_notes(
    runner: CliRunner,
    repo_dir: Path,
) -> None:
    result = runner.invoke(
        app,
        ["init", "--yes", "--template", "github-agent-workflows", "--backlog", "custom"],
    )
    assert result.exit_code == 0, result.output

    setup = (repo_dir / ".eden" / "github" / "SETUP_TRACKER.md").read_text(encoding="utf-8")
    dockerfile = (repo_dir / ".eden" / "Dockerfile").read_text(encoding="utf-8")
    env_ex = (repo_dir / ".eden" / ".env.example").read_text(encoding="utf-8")
    assert "custom" in setup
    assert "<TODO" in dockerfile
    assert "YOUR_TRACKER_TOKEN" in env_ex


def test_init_github_agent_workflows_refuses_existing_workflow_before_writing_eden(
    runner: CliRunner,
    repo_dir: Path,
) -> None:
    workflows = repo_dir / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "eden-agent-implement.yml").write_text("existing\n", encoding="utf-8")

    result = runner.invoke(
        app,
        ["init", "--yes", "--template", "github-agent-workflows", "--backlog", "github"],
    )

    assert result.exit_code == 1
    assert not (repo_dir / ".eden").exists()
