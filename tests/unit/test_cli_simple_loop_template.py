"""Verify the simple-loop template renderer + backlog registry."""

from __future__ import annotations

import pytest

from eden.cli._templates._backlog import (
    get_backlog_manager,
    list_backlog_managers,
)
from eden.cli._templates.simple_loop import render_simple_loop

pytestmark = pytest.mark.unit


def test_backlog_registry_has_github_and_beads() -> None:
    names = {m.name for m in list_backlog_managers()}
    assert names == {"github", "beads"}


def test_get_backlog_manager_returns_known() -> None:
    gh = get_backlog_manager("github")
    assert gh.label == "GitHub Issues"
    assert "gh issue list" in gh.list_tasks_command


def test_get_backlog_manager_unknown_raises() -> None:
    with pytest.raises(KeyError):
        get_backlog_manager("jira")  # type: ignore[arg-type]


def test_render_simple_loop_files_all_present() -> None:
    bg = get_backlog_manager("github")
    files = render_simple_loop(
        sandbox="docker",
        agent="claude-code",
        model="claude-opus-4-7",
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


def test_render_simple_loop_env_example_includes_backlog_lines() -> None:
    bg = get_backlog_manager("github")
    files = render_simple_loop(
        sandbox="docker",
        agent="claude-code",
        model="m",
        image_name="eden:t",
        backlog=bg,
    )
    env_ex = files[".env.example"]
    assert "GH_TOKEN" in env_ex
    assert "ANTHROPIC_API_KEY" in env_ex
