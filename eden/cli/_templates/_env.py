"""Per-agent ``.env.example`` snippets shared by all eden init templates.

Each template assembles its own ``.env.example`` body by concatenating:

1. A short header explaining the file's purpose;
2. The agent-specific block from :data:`AGENT_ENV_EXAMPLE`;
3. The selected backlog manager's ``env_example_lines``.

Hoisted out of the per-template ``_BASE_ENV`` constants so adding a new
agent or rotating a key only requires editing one map.
"""

from __future__ import annotations

AGENT_ENV_EXAMPLE: dict[str, str] = {
    "claude-code": (
        "# Anthropic API key (required for claude-code)\n# ANTHROPIC_API_KEY=sk-ant-...\n"
    ),
    "codex": "# OpenAI API key (required for codex)\n# OPENAI_API_KEY=sk-...\n",
    "opencode": "# Provider key for the model you've configured opencode to use\n",
    "pi": "# pi credentials\n",
    "cursor": "# Cursor CLI credentials\n# CURSOR_API_KEY=...\n",
    "copilot": "# GitHub Copilot CLI credentials\n# GITHUB_TOKEN=ghp_...\n",
}

ENV_EXAMPLE_HEADER = "# Copy this file to .env and fill in the values your agent needs.\n\n"


def render_env_example(*, agent: str, backlog_lines: str) -> str:
    """Assemble the full ``.env.example`` body for a template.

    ``backlog_lines`` is the ``env_example_lines`` field of the selected
    :class:`BacklogManager`. Empty string for backlog managers that need
    no additional credentials (e.g. inline tasks).
    """
    body = ENV_EXAMPLE_HEADER + AGENT_ENV_EXAMPLE.get(agent, "")
    if backlog_lines:
        body += "\n" + backlog_lines
    return body


__all__ = ["AGENT_ENV_EXAMPLE", "ENV_EXAMPLE_HEADER", "render_env_example"]
