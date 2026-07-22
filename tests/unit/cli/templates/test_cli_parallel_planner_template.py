"""Verify the parallel-planner template renderer + init wiring."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest
from typer.testing import CliRunner

from eden.cli._templates._backlog import get_backlog_manager
from eden.cli._templates.parallel_planner import render_parallel_planner
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
    files = render_parallel_planner(
        sandbox="docker",
        agent="claude-code",
        model="m",
        image_name="eden:t",
        backlog=get_backlog_manager("github"),
    )
    assert set(files.keys()) == {
        "Dockerfile",
        "plan-prompt.md",
        "implement-prompt.md",
        "merge-prompt.md",
        "main.py",
        ".env.example",
        ".gitignore",
    }


def test_render_parallel_planner_exact_output() -> None:
    files = render_parallel_planner(
        sandbox="docker",
        agent="claude-code",
        model="m",
        image_name="eden:test",
        backlog=get_backlog_manager("github"),
    )
    rendered = "".join(f"{path}\0{contents}\0" for path, contents in sorted(files.items()))
    assert sha256(rendered.encode()).hexdigest() == (
        "295f22c31788cd3d606172b5d106bfa7d2a3fe91a6d1e0d4ce0bf4868857263f"
    )


def test_main_py_uses_thread_pool_and_output_object() -> None:
    files = render_parallel_planner(
        sandbox="docker",
        agent="claude-code",
        model="m",
        image_name="eden:t",
        backlog=get_backlog_manager("github"),
    )
    main = files["main.py"]
    assert "ThreadPoolExecutor" in main
    assert "Output.object" in main
    assert "schema=_validate_plan" in main
    assert "BranchStrategy.named" in main


def test_plan_prompt_threads_list_tasks_command() -> None:
    files = render_parallel_planner(
        sandbox="docker",
        agent="claude-code",
        model="m",
        image_name="eden:t",
        backlog=get_backlog_manager("github"),
    )
    plan = files["plan-prompt.md"]
    assert "gh issue list" in plan
    assert "Do not add a slug or any other suffix" in plan
    assert "must be deterministic" in plan
    # The "already filtered" hint keeps the planner from re-querying the
    # tracker and picking up tasks outside the configured filter.
    assert "already been filtered" in plan


def test_implement_prompt_substitutes_id_placeholder() -> None:
    files = render_parallel_planner(
        sandbox="docker",
        agent="claude-code",
        model="m",
        image_name="eden:t",
        backlog=get_backlog_manager("github"),
    )
    impl = files["implement-prompt.md"]
    # The view-task command's <ID> is replaced with {{TASK_ID}} so each
    # implementer's prompt expands to view its own task.
    assert "gh issue view {{TASK_ID}}" in impl


def test_merge_prompt_lists_branches_and_tasks_placeholders() -> None:
    files = render_parallel_planner(
        sandbox="docker",
        agent="claude-code",
        model="m",
        image_name="eden:t",
        backlog=get_backlog_manager("github"),
    )
    merge = files["merge-prompt.md"]
    assert "{{BRANCHES}}" in merge
    assert "{{TASKS}}" in merge


def test_init_writes_parallel_planner_files(runner: CliRunner, repo_dir: Path) -> None:
    result = runner.invoke(
        app,
        [
            "init",
            "--yes",
            "--template",
            "parallel-planner",
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
        "merge-prompt.md",
        "main.py",
        ".env.example",
        ".gitignore",
    }
    assert {p.name for p in eden_dir.iterdir()} == expected


def test_init_parallel_planner_default_backlog_is_github(runner: CliRunner, repo_dir: Path) -> None:
    result = runner.invoke(
        app,
        ["init", "--yes", "--template", "parallel-planner"],
    )
    assert result.exit_code == 0, result.output
    plan = (repo_dir / ".eden" / "plan-prompt.md").read_text(encoding="utf-8")
    assert "gh issue list" in plan
