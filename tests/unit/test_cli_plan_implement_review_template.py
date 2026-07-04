"""Verify plan-implement-review template scaffolding."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from eden.cli._templates._backlog import get_backlog_manager
from eden.cli._templates.plan_implement_review import render_plan_implement_review
from eden.cli.main import app

pytestmark = pytest.mark.unit


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def repo_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    repo = tmp_path / "my-repo"
    repo.mkdir()
    monkeypatch.chdir(repo)
    return repo


def test_render_files_all_present() -> None:
    files = render_plan_implement_review(
        sandbox="docker",
        agent="claude-code",
        model="claude-opus-4-8",
        image_name="eden:test",
        backlog=get_backlog_manager("github"),
    )
    expected = {
        "Dockerfile",
        "plan-prompt.md",
        "implement-prompt.md",
        "review-prompt.md",
        "CODING_STANDARDS.md",
        "main.py",
        ".env.example",
        ".gitignore",
    }
    assert set(files) == expected


def test_plan_prompt_extracts_via_xml_tag() -> None:
    files = render_plan_implement_review(
        sandbox="docker",
        agent="claude-code",
        model="m",
        image_name="eden:t",
        backlog=get_backlog_manager("github"),
    )
    assert "<plan>" in files["plan-prompt.md"]
    assert "</plan>" in files["plan-prompt.md"]


def test_implement_prompt_substitutes_PLAN_arg() -> None:
    files = render_plan_implement_review(
        sandbox="docker",
        agent="claude-code",
        model="m",
        image_name="eden:t",
        backlog=get_backlog_manager("github"),
    )
    # eden's prompt-arg substitution uses {{KEY}}; the implementer prompt
    # carries the planner's output through `prompt_args={"PLAN": ...}`.
    assert "{{PLAN}}" in files["implement-prompt.md"]


def test_review_prompt_uses_branch_substitutions_and_plan() -> None:
    files = render_plan_implement_review(
        sandbox="docker",
        agent="claude-code",
        model="m",
        image_name="eden:t",
        backlog=get_backlog_manager("github"),
    )
    body = files["review-prompt.md"]
    assert "{{SOURCE_BRANCH}}" in body
    assert "{{TARGET_BRANCH}}" in body
    assert "{{PLAN}}" in body  # reviewer also sees the plan


def test_main_py_threads_three_sandbox_runs() -> None:
    files = render_plan_implement_review(
        sandbox="docker",
        agent="claude-code",
        model="m",
        image_name="eden:t",
        backlog=get_backlog_manager("github"),
    )
    main = files["main.py"]
    # Three sequential sandbox.run() calls in the right order.
    assert main.count("sandbox.run(") == 3
    assert main.index("planner") < main.index("implementer") < main.index("reviewer")
    assert 'Output.string(tag="plan")' in main
    assert '"PLAN": plan.output' in main


def test_main_py_threads_create_sandbox_and_named_branch() -> None:
    files = render_plan_implement_review(
        sandbox="docker",
        agent="claude-code",
        model="m",
        image_name="eden:t",
        backlog=get_backlog_manager("github"),
    )
    main = files["main.py"]
    assert "create_sandbox(" in main
    assert "BranchStrategy.named" in main
    assert "eden/pir/" in main


def test_init_writes_plan_implement_review_files(runner: CliRunner, repo_dir: Path) -> None:
    result = runner.invoke(
        app,
        [
            "init",
            "--yes",
            "--sandbox",
            "docker",
            "--agent",
            "claude-code",
            "--template",
            "plan-implement-review",
            "--backlog",
            "github",
        ],
    )
    assert result.exit_code == 0, result.output
    eden_dir = repo_dir / ".eden"
    expected = {
        "Dockerfile",
        "plan-prompt.md",
        "implement-prompt.md",
        "review-prompt.md",
        "CODING_STANDARDS.md",
        "main.py",
        ".env.example",
        ".gitignore",
    }
    assert {p.name for p in eden_dir.iterdir()} == expected


def test_render_rejects_unsupported_agent() -> None:
    with pytest.raises(ValueError, match="unsupported agent"):
        render_plan_implement_review(
            sandbox="docker",
            agent="not-an-agent",
            model="m",
            image_name="eden:t",
            backlog=get_backlog_manager("github"),
        )
