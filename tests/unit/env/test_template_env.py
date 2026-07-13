"""Verify the shared _env render helper for eden init templates."""

from __future__ import annotations

import pytest

from eden.cli._templates._env import (
    AGENT_ENV_EXAMPLE,
    ENV_EXAMPLE_HEADER,
    render_env_example,
)

pytestmark = pytest.mark.unit


def test_header_starts_the_body() -> None:
    out = render_env_example(agent="claude-code", backlog_lines="")
    assert out.startswith(ENV_EXAMPLE_HEADER)


def test_known_agent_appends_its_block() -> None:
    out = render_env_example(agent="codex", backlog_lines="")
    assert "OPENAI_API_KEY" in out


def test_unknown_agent_emits_header_only() -> None:
    out = render_env_example(agent="not-a-real-agent", backlog_lines="")
    assert out == ENV_EXAMPLE_HEADER


def test_backlog_lines_appended_when_non_empty() -> None:
    out = render_env_example(agent="claude-code", backlog_lines="# GH_TOKEN=\n")
    assert out.endswith("\n# GH_TOKEN=\n")
    # Separated from agent block by a blank line.
    assert "\n\n# GH_TOKEN=\n" in out


def test_backlog_lines_omitted_when_empty() -> None:
    out = render_env_example(agent="claude-code", backlog_lines="")
    # Should end with the agent block, not a trailing extra newline from
    # an empty backlog concat.
    assert out == ENV_EXAMPLE_HEADER + AGENT_ENV_EXAMPLE["claude-code"]


def test_all_four_known_agents_have_entries() -> None:
    for name in ("claude-code", "codex", "opencode", "pi"):
        assert name in AGENT_ENV_EXAMPLE, name
