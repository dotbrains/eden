"""Verify the simple-loop template renderer + backlog registry."""

from __future__ import annotations

import pytest

from eden.cli._templates._backlog import (
    get_backlog_manager,
    list_backlog_managers,
)
from eden.cli._templates.simple_loop import render_simple_loop

pytestmark = pytest.mark.unit


def test_backlog_registry_includes_github_and_beads() -> None:
    """github and beads are the original two; new entries may be added freely."""
    names = {m.name for m in list_backlog_managers()}
    assert {"github", "beads"} <= names


def test_get_backlog_manager_returns_known() -> None:
    gh = get_backlog_manager("github")
    assert gh.label == "GitHub Issues"
    assert "gh issue list" in gh.list_tasks_command


def test_get_backlog_manager_unknown_raises() -> None:
    with pytest.raises(KeyError):
        get_backlog_manager("trello-with-extra-cheese")  # type: ignore[arg-type]


def test_render_simple_loop_files_all_present() -> None:
    bg = get_backlog_manager("github")
    files = render_simple_loop(
        sandbox="docker",
        agent="claude-code",
        model="claude-opus-4-8",
        image_name="eden:test",
        backlog=bg,
    )
    assert set(files.keys()) == {
        "Dockerfile",
        "prompt.md",
        "main.py",
        ".env.example",
        ".gitignore",
    }


def test_render_simple_loop_dockerfile_threads_backlog_install() -> None:
    bg = get_backlog_manager("github")
    files = render_simple_loop(
        sandbox="docker",
        agent="claude-code",
        model="m",
        image_name="eden:t",
        backlog=bg,
    )
    df = files["Dockerfile"]
    assert "Install GitHub CLI" in df
    assert "FROM python:3.13-slim" in df


def test_render_simple_loop_prompt_threads_backlog_commands() -> None:
    bg = get_backlog_manager("beads")
    files = render_simple_loop(
        sandbox="docker",
        agent="claude-code",
        model="m",
        image_name="eden:t",
        backlog=bg,
    )
    prompt = files["prompt.md"]
    assert "bd ready --json" in prompt
    assert "bd show <ID>" in prompt
    assert "bd close <ID>" in prompt
    # The filtered-list guard keeps the agent from re-querying the tracker
    # with a broader filter when the configured list comes back empty.
    assert "already been filtered" in prompt
    assert "sole source of truth" in prompt
    assert "If the list is empty, there is nothing to do" in prompt


def test_render_simple_loop_main_py_threads_agent_factory() -> None:
    bg = get_backlog_manager("github")
    files = render_simple_loop(
        sandbox="docker",
        agent="opencode",
        model="claude-sonnet-4",
        image_name="eden:t",
        backlog=bg,
    )
    main = files["main.py"]
    assert "from eden import run, opencode" in main
    assert 'opencode("claude-sonnet-4")' in main
    assert "from eden.sandboxes import docker as sandbox_provider" in main


def test_linear_backlog_helpers_referenced_in_commands() -> None:
    bg = get_backlog_manager("linear")
    assert bg.label == "Linear"
    assert bg.list_tasks_command == "linear-list"
    assert bg.view_task_command == "linear-view <ID>"
    assert bg.close_task_command == "linear-close <ID>"
    assert "LINEAR_API_KEY" in bg.env_example_lines


def test_linear_dockerfile_installs_helper_scripts() -> None:
    bg = get_backlog_manager("linear")
    df = bg.dockerfile_install
    assert "linear-list" in df
    assert "linear-view" in df
    assert "linear-close" in df
    assert "jq" in df  # GraphQL response parsing


def test_jira_backlog_uses_jira_cli() -> None:
    bg = get_backlog_manager("jira")
    assert bg.label == "Jira"
    assert "jira issue list" in bg.list_tasks_command
    assert bg.view_task_command == "jira issue view <ID>"
    assert "jira issue move" in bg.close_task_command
    assert "JIRA_API_TOKEN" in bg.env_example_lines


def test_jira_dockerfile_installs_jira_cli() -> None:
    bg = get_backlog_manager("jira")
    assert "jira-cli" in bg.dockerfile_install


def test_render_simple_loop_with_linear() -> None:
    bg = get_backlog_manager("linear")
    files = render_simple_loop(
        sandbox="docker",
        agent="claude-code",
        model="m",
        image_name="eden:t",
        backlog=bg,
    )
    prompt = files["prompt.md"]
    assert "linear-list" in prompt
    assert "linear-view <ID>" in prompt
    assert "linear-close <ID>" in prompt


def test_render_simple_loop_with_jira() -> None:
    bg = get_backlog_manager("jira")
    files = render_simple_loop(
        sandbox="docker",
        agent="claude-code",
        model="m",
        image_name="eden:t",
        backlog=bg,
    )
    prompt = files["prompt.md"]
    assert "jira issue list" in prompt
    assert "jira issue view <ID>" in prompt
    assert "jira issue move" in prompt
