"""Verify the sequential-reviewer template renderer + init wiring."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from eden.cli._templates._backlog import get_backlog_manager
from eden.cli._templates.sequential_reviewer import render_sequential_reviewer
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
    bg = get_backlog_manager("github")
    files = render_sequential_reviewer(
        sandbox="docker",
        agent="claude-code",
        model="m",
        image_name="eden:t",
        backlog=bg,
    )
    assert set(files.keys()) == {
        "Dockerfile",
        "implement-prompt.md",
        "review-prompt.md",
        "CODING_STANDARDS.md",
        "main.py",
        ".env.example",
        ".gitignore",
    }


def test_review_prompt_uses_source_target_branch_substitutions() -> None:
    files = render_sequential_reviewer(
        sandbox="docker",
        agent="claude-code",
        model="m",
        image_name="eden:t",
        backlog=get_backlog_manager("github"),
    )
    review = files["review-prompt.md"]
    assert "{{SOURCE_BRANCH}}" in review
    assert "{{TARGET_BRANCH}}" in review


def test_main_py_threads_create_sandbox_and_named_branch() -> None:
    files = render_sequential_reviewer(
        sandbox="docker",
        agent="claude-code",
        model="claude-opus-4-7",
        image_name="eden:t",
        backlog=get_backlog_manager("github"),
    )
    main = files["main.py"]
    assert "from eden import claude_code, create_sandbox" in main
    assert "BranchStrategy.named(branch)" in main
    assert 'claude_code("claude-opus-4-7")' in main
    # Two sandbox.run() calls (implementer + reviewer)
    assert main.count("sandbox.run(") == 2


def test_implement_prompt_threads_backlog_commands() -> None:
    files = render_sequential_reviewer(
        sandbox="docker",
        agent="claude-code",
        model="m",
        image_name="eden:t",
        backlog=get_backlog_manager("beads"),
    )
    impl = files["implement-prompt.md"]
    assert "bd ready --json" in impl
    assert "bd close <ID>" in impl


def test_init_writes_sequential_reviewer_files(
    runner: CliRunner, repo_dir: Path
) -> None:
    result = runner.invoke(
        app,
        [
            "init",
            "--yes",
            "--template",
            "sequential-reviewer",
            "--backlog",
            "github",
        ],
    )
    assert result.exit_code == 0, result.output
    eden_dir = repo_dir / ".eden"
    expected = {
        "Dockerfile",
        "implement-prompt.md",
        "review-prompt.md",
        "CODING_STANDARDS.md",
        "main.py",
        ".env.example",
        ".gitignore",
    }
    assert {p.name for p in eden_dir.iterdir()} == expected


def test_init_sequential_reviewer_requires_backlog(
    runner: CliRunner, repo_dir: Path
) -> None:
    result = runner.invoke(
        app,
        [
            "init",
            "--yes",
            "--template",
            "sequential-reviewer",
            "--backlog",
            "jira",
        ],
    )
    assert result.exit_code != 0


def test_init_sequential_reviewer_default_backlog_is_github(
    runner: CliRunner, repo_dir: Path
) -> None:
    result = runner.invoke(
        app,
        ["init", "--yes", "--template", "sequential-reviewer"],
    )
    assert result.exit_code == 0, result.output
    impl = (repo_dir / ".eden" / "implement-prompt.md").read_text(encoding="utf-8")
    assert "gh issue list" in impl
