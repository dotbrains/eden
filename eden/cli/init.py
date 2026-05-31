"""`eden init` — scaffold a `.eden/` directory in the current repo."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import typer
from rich.console import Console

from eden.cli._templates._backlog import (
    BacklogName,
    get_backlog_manager,
    list_backlog_managers,
)
from eden.cli._templates.blank import render_blank
from eden.cli._templates.github_agent_workflows import render_github_agent_workflows
from eden.cli._templates.parallel_planner import render_parallel_planner
from eden.cli._templates.parallel_planner_with_review import (
    render_parallel_planner_with_review,
)
from eden.cli._templates.plan_implement_review import render_plan_implement_review
from eden.cli._templates.sequential_reviewer import render_sequential_reviewer
from eden.cli._templates.simple_loop import render_simple_loop

console = Console(stderr=True)


_VALID_SANDBOXES = ("docker", "podman")
_VALID_AGENTS = ("claude-code", "codex", "opencode", "pi")
_VALID_TEMPLATES = (
    "blank",
    "simple-loop",
    "sequential-reviewer",
    "parallel-planner",
    "parallel-planner-with-review",
    "plan-implement-review",
    "github-agent-workflows",
)
_TEMPLATES_REQUIRING_BACKLOG = {
    "simple-loop",
    "sequential-reviewer",
    "parallel-planner",
    "parallel-planner-with-review",
    "plan-implement-review",
    "github-agent-workflows",
}
_VALID_BACKLOGS = tuple(b.name for b in list_backlog_managers())
_TemplateRenderer = Callable[..., dict[str, str]]


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


_AGENTS: dict[str, AgentMetadata] = {
    "claude-code": AgentMetadata(
        name="claude-code",
        label="Claude Code",
        default_model="claude-opus-4-7",
    ),
    "codex": AgentMetadata(name="codex", label="Codex", default_model="gpt-5"),
    "opencode": AgentMetadata(name="opencode", label="opencode", default_model="claude-opus-4"),
    "pi": AgentMetadata(name="pi", label="Pi", default_model="pi-3.5"),
}

_TEMPLATE_METADATA: dict[str, TemplateMetadata] = {
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

_TEMPLATE_RENDERERS: dict[str, _TemplateRenderer] = {
    "blank": render_blank,
    "simple-loop": render_simple_loop,
    "sequential-reviewer": render_sequential_reviewer,
    "parallel-planner": render_parallel_planner,
    "parallel-planner-with-review": render_parallel_planner_with_review,
    "plan-implement-review": render_plan_implement_review,
    "github-agent-workflows": render_github_agent_workflows,
}


def _default_model(agent: str) -> str:
    try:
        return _AGENTS[agent].default_model
    except KeyError as exc:
        raise typer.BadParameter(
            f"agent must be one of {list(_VALID_AGENTS)}, got {agent!r}",
        ) from exc


def _detect_package_manager(repo: Path) -> str:
    """Return npm/pnpm/yarn/bun using package.json or lockfiles."""
    package_json = repo / "package.json"
    if package_json.exists():
        try:
            raw = json.loads(package_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw = {}
        package_manager = raw.get("packageManager")
        if isinstance(package_manager, str):
            manager = package_manager.split("@", 1)[0]
            if manager in {"npm", "pnpm", "yarn", "bun"}:
                return manager
    lockfiles = (
        ("bun.lockb", "bun"),
        ("bun.lock", "bun"),
        ("pnpm-lock.yaml", "pnpm"),
        ("yarn.lock", "yarn"),
        ("package-lock.json", "npm"),
    )
    for filename, manager in lockfiles:
        if (repo / filename).exists():
            return manager
    return "npm"


def _add_dependency_command(package_manager: str, dependency: str) -> str:
    if package_manager == "pnpm":
        return f"pnpm add {dependency}"
    if package_manager == "yarn":
        return f"yarn add {dependency}"
    if package_manager == "bun":
        return f"bun add {dependency}"
    return f"npm install {dependency}"


def _has_host_dependency(repo: Path, dependency: str) -> bool:
    package_json = repo / "package.json"
    if not package_json.exists():
        return False
    try:
        raw = json.loads(package_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    for key in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        deps = raw.get(key)
        if isinstance(deps, dict) and dependency in deps:
            return True
    return False


def _render_template(
    *,
    template: str,
    sandbox: str,
    agent: str,
    model: str,
    image_name: str,
    backlog: str | None,
) -> dict[str, str]:
    renderer = _TEMPLATE_RENDERERS[template]
    common = {
        "sandbox": sandbox,
        "agent": agent,
        "model": model,
        "image_name": image_name,
    }
    if template not in _TEMPLATES_REQUIRING_BACKLOG:
        return renderer(**common)
    assert backlog is not None
    return renderer(
        **common,
        backlog=get_backlog_manager(cast(BacklogName, backlog)),
    )


def init_command(
    sandbox: str | None = typer.Option(None, "--sandbox", help="Container runtime"),
    agent: str | None = typer.Option(None, "--agent", help="Agent factory"),
    model: str | None = typer.Option(None, "--model", help="Model identifier"),
    template: str | None = typer.Option(None, "--template", help="Scaffold template"),
    backlog: str | None = typer.Option(
        None,
        "--backlog",
        help=(
            "Backlog manager: one of github, beads, linear, jira, or custom "
            "(custom scaffolds <TODO> stubs the agent wires up on first run). "
            "Only used by templates that read a backlog."
        ),
    ),
    image_name: str | None = typer.Option(None, "--image-name", help="Docker image tag"),
    yes: bool = typer.Option(False, "--yes", help="Accept all defaults"),
) -> None:
    """Scaffold .eden/ in the current repo."""
    target = Path.cwd() / ".eden"
    if target.exists():
        console.print(f"[red]refusing to overwrite existing {target}[/red]")
        raise typer.Exit(code=1)

    # Resolve flags interactively if not supplied (and not --yes).
    if not yes:
        sandbox = sandbox or typer.prompt("Sandbox", default="docker")
        agent = agent or typer.prompt("Agent", default="claude-code")
        # Default model depends on agent; resolve agent first so the prompt
        # default reflects the chosen agent.
        model = model or typer.prompt("Model", default=_default_model(agent))
        template = template or typer.prompt("Template", default="blank")
        if template in _TEMPLATES_REQUIRING_BACKLOG:
            backlog = backlog or typer.prompt("Backlog manager", default="github")
    else:
        sandbox = sandbox or "docker"
        agent = agent or "claude-code"
        model = model or _default_model(agent)
        template = template or "blank"
        if template in _TEMPLATES_REQUIRING_BACKLOG:
            backlog = backlog or "github"

    image_name = image_name or f"eden:{Path.cwd().name.lower()}"

    if sandbox not in _VALID_SANDBOXES:
        raise typer.BadParameter(
            f"sandbox must be one of {list(_VALID_SANDBOXES)}, got {sandbox!r}",
        )
    if agent not in _VALID_AGENTS:
        raise typer.BadParameter(
            f"agent must be one of {list(_VALID_AGENTS)}, got {agent!r}",
        )
    if template not in _VALID_TEMPLATES:
        raise typer.BadParameter(
            f"template must be one of {list(_VALID_TEMPLATES)}, got {template!r}",
        )
    if template in _TEMPLATES_REQUIRING_BACKLOG:
        if backlog not in _VALID_BACKLOGS:
            raise typer.BadParameter(
                f"backlog must be one of {list(_VALID_BACKLOGS)}, got {backlog!r}",
            )

    files = _render_template(
        template=template,
        sandbox=sandbox,
        agent=agent,
        model=model,
        image_name=image_name,
        backlog=backlog,
    )
    repo = Path.cwd().resolve()
    outputs: list[tuple[Path, str]] = []
    for name, contents in files.items():
        out = (target / name).resolve()
        if not out.is_relative_to(repo):
            console.print(f"[red]refusing to write outside repo: {out}[/red]")
            raise typer.Exit(code=1)
        if out.exists():
            console.print(f"[red]refusing to overwrite existing {out}[/red]")
            raise typer.Exit(code=1)
        outputs.append((out, contents))

    target.mkdir(parents=True)
    for out, contents in outputs:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(contents, encoding="utf-8")

    typer.secho(f"✓ scaffolded {target}", fg="green")
    meta = _TEMPLATE_METADATA[template]
    typer.echo(f"Template: {meta.name} - {meta.description}")
    typer.echo("Next steps:")
    typer.echo("  1. cp .eden/.env.example .env  # then fill in your API keys")
    step = 2
    dependencies = tuple(dep for dep in meta.dependencies if not _has_host_dependency(repo, dep))
    if dependencies:
        package_manager = _detect_package_manager(repo)
        for dependency in dependencies:
            typer.echo(f"  {step}. {_add_dependency_command(package_manager, dependency)}")
            step += 1
    typer.echo(
        f"  {step}. {sandbox} build "
        f"--build-arg AGENT_UID=$(id -u) --build-arg AGENT_GID=$(id -g) "
        f"-t {image_name} -f .eden/Dockerfile ."
    )
    step += 1
    typer.echo(f"  {step}. python .eden/main.py")
