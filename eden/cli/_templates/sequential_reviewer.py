"""sequential-reviewer template content.

A two-phase loop per task: an implementer agent commits changes on a named
branch, then a reviewer agent inspects the diff and approves or corrects.
Both agents share one ``Sandbox`` so the second run sees the implementer's
working tree directly.
"""

from __future__ import annotations

from eden.cli._templates._backlog import BacklogManager
from eden.cli._templates._env import render_env_example
from eden.cli._templates.sequential_reviewer_assets import (
    CODING_STANDARDS,
    DOCKERFILE,
    GITIGNORE,
    IMPLEMENT_PROMPT,
    MAIN_PY,
    REVIEW_PROMPT,
)

_AGENT_IMPORT: dict[str, str] = {
    "claude-code": "claude_code",
    "codex": "codex",
    "opencode": "opencode",
    "pi": "pi",
}

_AGENT_CALL: dict[str, str] = {
    "claude-code": 'claude_code("{model}")',
    "codex": 'codex("{model}")',
    "opencode": 'opencode("{model}")',
    "pi": 'pi("{model}")',
}


def render_sequential_reviewer(
    *,
    sandbox: str,
    agent: str,
    model: str,
    image_name: str,
    backlog: BacklogManager,
) -> dict[str, str]:
    """Return ``{filename: contents}`` for the sequential-reviewer files."""
    if agent not in _AGENT_IMPORT:
        raise ValueError(f"unsupported agent for sequential-reviewer: {agent!r}")
    image_arg = f'image="{image_name}"' if sandbox in ("docker", "podman") else ""
    env_example = render_env_example(agent=agent, backlog_lines=backlog.env_example_lines)

    agent_call = _AGENT_CALL[agent].format(model=model)
    return {
        "Dockerfile": DOCKERFILE.format(backlog_install=backlog.dockerfile_install),
        "implement-prompt.md": IMPLEMENT_PROMPT.format(
            list_tasks_command=backlog.list_tasks_command,
            close_task_command=backlog.close_task_command,
        ),
        "review-prompt.md": REVIEW_PROMPT,
        "CODING_STANDARDS.md": CODING_STANDARDS,
        "main.py": MAIN_PY.format(
            sandbox=sandbox,
            image_arg=image_arg,
            agent_call=agent_call,
        ),
        ".env.example": env_example,
        ".gitignore": GITIGNORE,
    }


__all__ = ["render_sequential_reviewer"]
