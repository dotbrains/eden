"""Verify the parallel-planner-with-review template renderer + init wiring."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from eden.cli._templates._backlog import get_backlog_manager
from eden.cli._templates.parallel_planner_with_review import (
    render_parallel_planner_with_review,
)
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


def _files() -> dict[str, str]:
    return render_parallel_planner_with_review(
        sandbox="docker",
        agent="claude-code",
        model="m",
        image_name="eden:t",
        backlog=get_backlog_manager("github"),
    )


def test_render_files_all_present() -> None:
    files = _files()
    assert set(files.keys()) == {
        "Dockerfile",
        "plan-prompt.md",
        "implement-prompt.md",
        "review-prompt.md",
        "merge-prompt.md",
        "CODING_STANDARDS.md",
        "main.py",
        ".env.example",
        ".gitignore",
    }


def test_main_py_uses_create_sandbox_and_per_branch_review() -> None:
    main = _files()["main.py"]
    # Per-branch review = each task runs implement + review in the *same*
    # sandbox (see _execute_and_review). create_sandbox is the giveaway.
    assert "create_sandbox" in main
    assert "_execute_and_review" in main
    assert "review-prompt.md" in main
    assert "ThreadPoolExecutor" in main
    assert "Output.object" in main


def test_review_prompt_references_source_and_target_branches() -> None:
    review = _files()["review-prompt.md"]
    assert "{{SOURCE_BRANCH}}" in review
    assert "{{TARGET_BRANCH}}" in review


def test_implement_prompt_substitutes_id_placeholder() -> None:
    impl = _files()["implement-prompt.md"]
    assert "gh issue view {{TASK_ID}}" in impl


def test_init_writes_parallel_planner_with_review_files(
    runner: CliRunner,
    repo_dir: Path,
) -> None:
    result = runner.invoke(
        app,
        [
            "init",
            "--yes",
            "--template",
            "parallel-planner-with-review",
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
        "merge-prompt.md",
        "CODING_STANDARDS.md",
        "main.py",
        ".env.example",
        ".gitignore",
    }
    assert {p.name for p in eden_dir.iterdir()} == expected
