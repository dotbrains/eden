"""GitHub label-driven agent workflow template for ``eden init``."""

from __future__ import annotations

from eden.cli._templates._backlog import BacklogManager
from eden.cli._templates._env import render_env_example
from eden.cli._templates._github_assets import (
    FACTORY_SCRIPT,
    IMPLEMENT_PROMPT,
    IMPLEMENT_SCRIPT,
    REVIEW_CONTRACT,
    REVIEW_PROMPT,
    REVIEW_SCRIPT,
    SETUP_TRACKER,
)
from eden.cli._templates._github_workflows import (
    IMPLEMENT_WORKFLOW,
    REVIEW_WORKFLOW,
    render_workflow,
)
from eden.cli._templates.plan_implement_review import (
    _CODING_STANDARDS,
    _DOCKERFILE,
    _GITIGNORE,
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


def render_github_agent_workflows(
    *,
    sandbox: str,
    agent: str,
    model: str,
    image_name: str,
    backlog: BacklogManager,
) -> dict[str, str]:
    """Return files for GitHub label-driven Eden agent workflows."""
    if agent not in _AGENT_IMPORT:
        raise ValueError(f"unsupported agent for github-agent-workflows: {agent!r}")
    agent_import = _AGENT_IMPORT[agent]
    agent_call = _AGENT_CALL[agent].format(model=model)
    image_arg = f'image="{image_name}"' if sandbox in ("docker", "podman") else ""
    env_example = render_env_example(agent=agent, backlog_lines=backlog.env_example_lines)
    script_args = {
        "agent_import": agent_import,
        "agent_call": agent_call,
        "sandbox": sandbox,
        "image_arg": image_arg,
    }
    return {
        "../.github/workflows/eden-agent-implement.yml": render_workflow(
            IMPLEMENT_WORKFLOW,
            image_name=image_name,
        ),
        "../.github/workflows/eden-agent-review.yml": render_workflow(
            REVIEW_WORKFLOW,
            image_name=image_name,
        ),
        "Dockerfile": _DOCKERFILE.format(backlog_install=backlog.dockerfile_install),
        "github/implement_issue.py": IMPLEMENT_SCRIPT.format(**script_args),
        "github/review_pr.py": REVIEW_SCRIPT.format(**script_args),
        "github/factory.py": FACTORY_SCRIPT.format(
            **script_args,
            list_tasks_command=backlog.list_tasks_command,
        ),
        "github/implement-issue.md": IMPLEMENT_PROMPT,
        "github/review-pr.md": REVIEW_PROMPT,
        "github/SETUP_TRACKER.md": SETUP_TRACKER.format(backlog_name=backlog.name),
        "github/REVIEW_OUTPUT.md": REVIEW_CONTRACT,
        "CODING_STANDARDS.md": _CODING_STANDARDS,
        ".env.example": env_example,
        ".gitignore": _GITIGNORE,
    }


__all__ = ["render_github_agent_workflows"]
