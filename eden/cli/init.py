"""`eden init` — scaffold a `.eden/` directory in the current repo."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import cast

import typer
from rich.console import Console

from eden.cli._image import build_image as _build_image
from eden.cli._init_scaffold import scaffold_init_files as _scaffold_init_files
from eden.cli._init_templates import (
    TEMPLATES_REQUIRING_BACKLOG as _TEMPLATES_REQUIRING_BACKLOG,
)
from eden.cli._init_templates import (
    default_model as _default_model,
)
from eden.cli._init_templates import (
    render_template as _render_template,
)
from eden.cli._init_validation import validate_init_options as _validate_init_options

console = Console(stderr=True)


def _resolve_option(
    value: str | None,
    *,
    flag: str,
    label: str,
    default: str,
    interactive: bool,
    yes: bool,
) -> str:
    """Resolve an init option from a flag, a prompt, or a default.

    Precedence: an explicit ``value`` always wins. Otherwise, when attached
    to a TTY (and not ``--yes``) we prompt with ``default``; under ``--yes``
    we take ``default`` silently. When stdin is not a TTY and the flag is
    absent, we fail fast naming the flag rather than hanging on (or aborting
    out of) the prompt library.
    """
    if value is not None:
        return value
    if interactive:
        return cast(str, typer.prompt(label, default=default))
    if yes:
        return default
    raise typer.BadParameter(
        f"{flag} is required when stdin is not a TTY; "
        f"pass {flag} or --yes to accept the default ({default!r})",
        param_hint=flag,
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
    build_image: bool = typer.Option(
        False,
        "--build-image",
        help="Build the scaffolded container image after writing .eden/.",
    ),
    yes: bool = typer.Option(False, "--yes", help="Accept all defaults"),
) -> None:
    """Scaffold .eden/ in the current repo."""
    target = Path.cwd() / ".eden"
    if target.exists():
        console.print(f"[red]refusing to overwrite existing {target}[/red]")
        raise typer.Exit(code=1)

    interactive = sys.stdin.isatty() and not yes
    sandbox = _resolve_option(
        sandbox,
        flag="--sandbox",
        label="Sandbox",
        default="docker",
        interactive=interactive,
        yes=yes,
    )
    agent = _resolve_option(
        agent,
        flag="--agent",
        label="Agent",
        default="claude-code",
        interactive=interactive,
        yes=yes,
    )
    # Default model depends on agent; resolve agent first so the prompt
    # default reflects the chosen agent.
    model = _resolve_option(
        model,
        flag="--model",
        label="Model",
        default=_default_model(agent),
        interactive=interactive,
        yes=yes,
    )
    template = _resolve_option(
        template,
        flag="--template",
        label="Template",
        default="blank",
        interactive=interactive,
        yes=yes,
    )
    if template in _TEMPLATES_REQUIRING_BACKLOG:
        backlog = _resolve_option(
            backlog,
            flag="--backlog",
            label="Backlog manager",
            default="github",
            interactive=interactive,
            yes=yes,
        )

    image_name = image_name or f"eden:{Path.cwd().name.lower()}"

    _validate_init_options(
        sandbox=sandbox,
        agent=agent,
        template=template,
        backlog=backlog,
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
    _scaffold_init_files(
        target=target,
        repo=repo,
        files=files,
        template=template,
        sandbox=sandbox,
        image_name=image_name,
    )
    if build_image:
        _build_image(binary=sandbox, image_name=image_name)
