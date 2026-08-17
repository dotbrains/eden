"""`eden routine save` — persist a named, reusable ``eden run`` invocation."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from eden.cli.routine._store import RoutineConfig, routine_path, save_routine
from eden.cli.run import (
    _DEFAULT_MODELS,
    _VALID_AGENTS,
    _VALID_BACKLOGS,
    _VALID_SANDBOXES,
    _VALID_TEMPLATES,
)

console = Console(stderr=True)


def save_command(
    name: str = typer.Argument(..., help="Routine name"),
    sandbox: str = typer.Option("docker", "--sandbox", help="Container runtime"),
    agent: str = typer.Option("claude-code", "--agent", help="Agent factory"),
    model: str | None = typer.Option(None, "--model", help="Model identifier"),
    template: str = typer.Option(
        "simple-loop", "--template", help="Template to run in-process (currently: simple-loop)"
    ),
    backlog: str = typer.Option(
        "github", "--backlog", help="Backlog manager (github, beads, linear, jira)"
    ),
    image_name: str | None = typer.Option(
        None, "--image-name", help="Container image (required for docker/podman sandboxes)"
    ),
    max_iterations: int = typer.Option(3, "--max-iterations", help="Maximum iteration loop turns"),
    idle_timeout: float = typer.Option(
        600.0, "--idle-timeout", help="Idle-timeout (seconds) before bailing"
    ),
    completion_timeout: float | None = typer.Option(
        60.0,
        "--completion-timeout",
        help="Grace window (seconds) after the completion signal; pass 0 to disable",
    ),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing routine"),
    cwd: Path | None = typer.Option(None, "--cwd", help="Repo to save the routine in"),  # noqa: B008
) -> None:
    """Save flags as a named routine under .eden/routines/<name>.json."""
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
    if sandbox in ("docker", "podman") and not image_name:
        raise typer.BadParameter(f"--image-name is required for --sandbox {sandbox}")

    repo = (cwd or Path.cwd()).resolve()
    try:
        target = routine_path(repo, name)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if target.exists() and not force:
        console.print(
            f"[red]routine {name!r} already exists at {target}[/red] — pass --force to overwrite."
        )
        raise typer.Exit(code=1)

    config = RoutineConfig(
        sandbox=sandbox,
        agent=agent,
        model=model or _DEFAULT_MODELS[agent],
        template=template,
        backlog=backlog,
        image_name=image_name,
        max_iterations=max_iterations,
        idle_timeout=idle_timeout,
        completion_timeout=completion_timeout,
    )
    path = save_routine(repo, name, config)
    console.print(f"[green]saved routine {name!r} to {path}[/green]")
