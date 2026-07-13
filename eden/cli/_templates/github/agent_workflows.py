"""GitHub label-driven agent workflow template for ``eden init``."""

from __future__ import annotations

from eden.cli._templates._backlog import BacklogManager
from eden.cli._templates._common import (
    GITIGNORE,
    render_agent_call,
    render_backlog_dockerfile,
    render_image_arg,
)
from eden.cli._templates._env import render_env_example
from eden.cli._templates._parallel_prompts import PARALLEL_CODING_STANDARDS
from eden.cli._templates.github._prompts import IMPLEMENT_PROMPT, REVIEW_PROMPT
from eden.cli._templates.github._scripts import FACTORY_SCRIPT, IMPLEMENT_SCRIPT, REVIEW_SCRIPT
from eden.cli._templates.github._support_docs import REVIEW_CONTRACT, SETUP_TRACKER
from eden.cli._templates.github._workflows import (
    IMPLEMENT_WORKFLOW,
    REVIEW_WORKFLOW,
    render_workflow,
)


def render_github_agent_workflows(
    *,
    sandbox: str,
    agent: str,
    model: str,
    image_name: str,
    backlog: BacklogManager,
) -> dict[str, str]:
    """Return files for GitHub label-driven Eden agent workflows."""
    agent_import, agent_call = render_agent_call(
        template="github-agent-workflows",
        agent=agent,
        model=model,
    )
    image_arg = render_image_arg(sandbox=sandbox, image_name=image_name)
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
        "Dockerfile": render_backlog_dockerfile(backlog),
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
        "CODING_STANDARDS.md": PARALLEL_CODING_STANDARDS,
        ".env.example": env_example,
        ".gitignore": GITIGNORE,
    }


__all__ = ["render_github_agent_workflows"]
