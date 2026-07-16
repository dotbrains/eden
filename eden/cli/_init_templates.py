"""Template metadata and rendering for ``eden init``."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

import typer

from eden.cli._templates._backlog import (
    BacklogName,
    get_backlog_manager,
    list_backlog_managers,
)
from eden.cli._templates.blank import render_blank
from eden.cli._templates.github import render_github_agent_workflows
from eden.cli._templates.parallel_planner import render_parallel_planner
from eden.cli._templates.parallel_planner_with_review import (
    render_parallel_planner_with_review,
)
from eden.cli._templates.plan_implement_review import render_plan_implement_review
from eden.cli._templates.sequential_reviewer import render_sequential_reviewer
from eden.cli._templates.simple_loop import render_simple_loop

VALID_SANDBOXES = ("docker", "podman")
VALID_AGENTS = ("claude-code", "codex", "opencode", "pi")
VALID_TEMPLATES = (
    "blank",
    "simple-loop",
    "sequential-reviewer",
    "parallel-planner",
    "parallel-planner-with-review",
    "plan-implement-review",
    "github-agent-workflows",
)
TEMPLATES_REQUIRING_BACKLOG = {
    "simple-loop",
    "sequential-reviewer",
    "parallel-planner",
    "parallel-planner-with-review",
    "plan-implement-review",
    "github-agent-workflows",
}
VALID_BACKLOGS = tuple(b.name for b in list_backlog_managers())
TemplateRenderer = Callable[..., dict[str, str]]


@dataclass(frozen=True)
class AgentMetadata:
    name: str
    label: str
    default_model: str


@dataclass(frozen=True)
class TemplateMetadata:
    name: str
    description: str
    dependencies: tuple[str, ...] = ()


AGENTS: dict[str, AgentMetadata] = {
    "claude-code": AgentMetadata(
        name="claude-code",
        label="Claude Code",
        default_model="claude-opus-4-8",
    ),
    "codex": AgentMetadata(name="codex", label="Codex", default_model="gpt-5.4"),
    "opencode": AgentMetadata(name="opencode", label="opencode", default_model="claude-opus-4"),
    "pi": AgentMetadata(name="pi", label="Pi", default_model="pi-3.5"),
}

TEMPLATE_METADATA: dict[str, TemplateMetadata] = {
    "blank": TemplateMetadata(
        name="blank",
        description="Bare scaffold; write your own prompt and orchestration.",
    ),
    "simple-loop": TemplateMetadata(
        name="simple-loop",
        description="Pick backlog items one by one and close them.",
    ),
    "sequential-reviewer": TemplateMetadata(
        name="sequential-reviewer",
        description="Implement backlog items with a review step after each.",
    ),
    "parallel-planner": TemplateMetadata(
        name="parallel-planner",
        description="Plan parallelizable tasks, execute branches, then merge.",
    ),
    "parallel-planner-with-review": TemplateMetadata(
        name="parallel-planner-with-review",
        description="Plan parallel tasks with per-branch review before merge.",
    ),
    "plan-implement-review": TemplateMetadata(
        name="plan-implement-review",
        description="Plan, implement, and review each item in sequence.",
    ),
    "github-agent-workflows": TemplateMetadata(
        name="github-agent-workflows",
        description="Create GitHub Actions workflows for Eden-powered agents.",
    ),
}

TEMPLATE_RENDERERS: dict[str, TemplateRenderer] = {
    "blank": render_blank,
    "simple-loop": render_simple_loop,
    "sequential-reviewer": render_sequential_reviewer,
    "parallel-planner": render_parallel_planner,
    "parallel-planner-with-review": render_parallel_planner_with_review,
    "plan-implement-review": render_plan_implement_review,
    "github-agent-workflows": render_github_agent_workflows,
}


def default_model(agent: str) -> str:
    try:
        return AGENTS[agent].default_model
    except KeyError as exc:
        raise typer.BadParameter(
            f"agent must be one of {list(VALID_AGENTS)}, got {agent!r}",
        ) from exc


def render_template(
    *,
    template: str,
    sandbox: str,
    agent: str,
    model: str,
    image_name: str,
    backlog: str | None,
) -> dict[str, str]:
    renderer = TEMPLATE_RENDERERS[template]
    common = {
        "sandbox": sandbox,
        "agent": agent,
        "model": model,
        "image_name": image_name,
    }
    if template not in TEMPLATES_REQUIRING_BACKLOG:
        return renderer(**common)
    assert backlog is not None
    return renderer(
        **common,
        backlog=get_backlog_manager(cast(BacklogName, backlog)),
    )
