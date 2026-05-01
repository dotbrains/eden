"""Top-level Typer application for the `eden` console script."""

from __future__ import annotations

import typer

from eden import __version__
from eden.cli.init import init_command

app = typer.Typer(
    name="eden",
    help="Python orchestrator for AI coding agents in sandboxed worktrees.",
    no_args_is_help=True,
    add_completion=False,
)

app.command(name="init", help="Scaffold .eden/ in the current repo.")(init_command)


@app.command(name="version", help="Print the eden version and exit.")
def version_command() -> None:
    typer.echo(__version__)
