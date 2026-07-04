"""`eden run` — run a template's iteration loop in-process.

Unlike ``eden init`` (which scaffolds files for the user to edit and run
themselves), ``eden run`` translates the same flags into an in-process
``eden.run()`` invocation. Useful for quick experiments and CI pipelines
where there's no value in committing a generated ``.eden/`` directory.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

import eden
from eden.cli._templates._backlog import (
    get_backlog_manager,
    list_backlog_managers,
)
from eden.cli._templates.simple_loop import render_simple_loop_prompt
from eden.providers._protocols import SandboxProvider

console = Console(stderr=True)


_VALID_SANDBOXES = ("docker", "podman", "no-sandbox")
_VALID_AGENTS = ("claude-code", "codex", "opencode", "pi")
_VALID_TEMPLATES = ("simple-loop",)
_VALID_BACKLOGS = tuple(b.name for b in list_backlog_managers())


def _build_agent(agent: str, model: str) -> eden.Agent:
    if agent == "claude-code":
        return eden.claude_code(model)
    if agent == "codex":
        return eden.codex(model)
    if agent == "opencode":
        return eden.opencode(model)
    if agent == "pi":
        return eden.pi(model)
    raise typer.BadParameter(
        f"agent must be one of {list(_VALID_AGENTS)}, got {agent!r}",
    )


def _build_sandbox(sandbox: str, image_name: str | None) -> SandboxProvider:
    if sandbox == "docker":
        if not image_name:
            raise typer.BadParameter("--image-name is required for --sandbox docker")
        from eden.sandboxes import docker

        return docker.provider(image=image_name)
    if sandbox == "podman":
        if not image_name:
            raise typer.BadParameter("--image-name is required for --sandbox podman")
        from eden.sandboxes import podman

        return podman.provider(image=image_name)
    if sandbox == "no-sandbox":
        from eden.sandboxes import no_sandbox

        return no_sandbox.provider()
    raise typer.BadParameter(
        f"sandbox must be one of {list(_VALID_SANDBOXES)}, got {sandbox!r}",
    )


def run_command(
    sandbox: str = typer.Option("docker", "--sandbox", help="Container runtime"),
    agent: str = typer.Option("claude-code", "--agent", help="Agent factory"),
    model: str | None = typer.Option(None, "--model", help="Model identifier"),
    template: str = typer.Option(
        "simple-loop",
        "--template",
        help="Template to run in-process (currently: simple-loop)",
    ),
    backlog: str = typer.Option(
        "github",
        "--backlog",
        help="Backlog manager (github, beads, linear, jira)",
    ),
    image_name: str | None = typer.Option(
        None,
        "--image-name",
        help="Container image (required for docker/podman sandboxes)",
    ),
    max_iterations: int = typer.Option(3, "--max-iterations", help="Maximum iteration loop turns"),
    idle_timeout: float = typer.Option(
        600.0, "--idle-timeout", help="Idle-timeout (seconds) before bailing"
    ),
    cwd: Path | None = typer.Option(None, "--cwd", help="Repo to run in"),  # noqa: B008
) -> None:
    """Run a template's iteration loop in-process via ``eden.run()``."""
    if template not in _VALID_TEMPLATES:
        raise typer.BadParameter(
            f"template must be one of {list(_VALID_TEMPLATES)}, got {template!r}",
        )
    if sandbox not in _VALID_SANDBOXES:
        raise typer.BadParameter(
            f"sandbox must be one of {list(_VALID_SANDBOXES)}, got {sandbox!r}",
        )
    if agent not in _VALID_AGENTS:
        raise typer.BadParameter(
            f"agent must be one of {list(_VALID_AGENTS)}, got {agent!r}",
        )
    if backlog not in _VALID_BACKLOGS:
        raise typer.BadParameter(
            f"backlog must be one of {list(_VALID_BACKLOGS)}, got {backlog!r}",
        )

    default_models: dict[str, str] = {
        "claude-code": "claude-opus-4-8",
        "codex": "gpt-5",
        "opencode": "claude-opus-4",
        "pi": "pi-3.5",
    }
    resolved_model = model or default_models[agent]

    agent_factory = _build_agent(agent, resolved_model)
    sandbox_provider = _build_sandbox(sandbox, image_name)
    backlog_manager = get_backlog_manager(backlog)
    prompt = render_simple_loop_prompt(backlog_manager)

    console.print(
        f"[cyan]eden run[/cyan] template={template} sandbox={sandbox} "
        f"agent={agent} model={resolved_model} backlog={backlog}"
    )

    result = eden.run(
        agent=agent_factory,
        sandbox=sandbox_provider,
        prompt=prompt,
        max_iterations=max_iterations,
        idle_timeout=idle_timeout,
        cwd=cwd,
    )

    typer.echo(f"Completion: {result.completion_signal}")
    typer.echo(f"Iterations: {len(result.iterations)}")
    typer.echo(f"Branch:     {result.branch}")
