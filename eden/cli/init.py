"""`eden init` — scaffold a `.eden/` directory in the current repo."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from eden.cli._templates.blank import render_blank

console = Console(stderr=True)


_VALID_SANDBOXES = ("docker", "podman")
_VALID_AGENTS = ("claude-code", "codex", "opencode", "pi")
_VALID_TEMPLATES = ("blank",)

_DEFAULT_MODEL: dict[str, str] = {
    "claude-code": "claude-opus-4-7",
    "codex": "gpt-5",
    "opencode": "claude-opus-4",
    "pi": "pi-3.5",
}


def init_command(
    sandbox: str | None = typer.Option(None, "--sandbox", help="Container runtime"),
    agent: str | None = typer.Option(None, "--agent", help="Agent factory"),
    model: str | None = typer.Option(None, "--model", help="Model identifier"),
    template: str | None = typer.Option(None, "--template", help="Scaffold template"),
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
        if agent not in _DEFAULT_MODEL:
            raise typer.BadParameter(
                f"agent must be one of {list(_VALID_AGENTS)}, got {agent!r}",
            )
        model = model or typer.prompt("Model", default=_DEFAULT_MODEL[agent])
        template = template or typer.prompt("Template", default="blank")
    else:
        sandbox = sandbox or "docker"
        agent = agent or "claude-code"
        if agent not in _DEFAULT_MODEL:
            raise typer.BadParameter(
                f"agent must be one of {list(_VALID_AGENTS)}, got {agent!r}",
            )
        model = model or _DEFAULT_MODEL[agent]
        template = template or "blank"

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
            f"only the 'blank' template is supported in v1, got {template!r}",
        )

    files = render_blank(
        sandbox=sandbox,
        agent=agent,
        model=model,
        image_name=image_name,
    )
    target.mkdir(parents=True)
    for name, contents in files.items():
        (target / name).write_text(contents, encoding="utf-8")

    typer.secho(f"✓ scaffolded {target}", fg="green")
    typer.echo("Next steps:")
    typer.echo("  1. cp .eden/.env.example .env  # then fill in your API keys")
    typer.echo(f"  2. docker build -t {image_name} -f .eden/Dockerfile .")
    typer.echo("  3. python .eden/main.py")
