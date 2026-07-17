"""Verify simple-loop template environment examples."""

from __future__ import annotations

import pytest

from eden.cli._templates._backlog import get_backlog_manager
from eden.cli._templates.simple_loop import render_simple_loop

pytestmark = pytest.mark.unit


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
    assert "CLAUDE_CODE_OAUTH_TOKEN" in env_ex
    assert "ANTHROPIC_API_KEY" in env_ex


@pytest.mark.parametrize(
    ("agent", "expected"),
    [
        ("cursor", "CURSOR_API_KEY"),
        ("copilot", "GITHUB_TOKEN"),
    ],
)
def test_render_simple_loop_env_example_includes_editor_agent_lines(
    agent: str,
    expected: str,
) -> None:
    bg = get_backlog_manager("beads")
    files = render_simple_loop(
        sandbox="docker",
        agent=agent,
        model="m",
        image_name="eden:t",
        backlog=bg,
    )
    assert expected in files[".env.example"]
