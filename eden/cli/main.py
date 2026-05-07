"""Top-level Typer application for the `eden` console script."""

from __future__ import annotations

import typer

from eden import __version__
from eden.cli.clean import clean_command
from eden.cli.cost import cost_command
from eden.cli.init import init_command
from eden.cli.replay import replay_command
from eden.cli.run import run_command

app = typer.Typer(
    name="eden",
    help="Python orchestrator for AI coding agents in sandboxed worktrees.",
    no_args_is_help=True,
    add_completion=False,
)

app.command(name="init", help="Scaffold .eden/ in the current repo.")(init_command)
app.command(
    name="run",
    help="Run a template's iteration loop in-process via eden.run().",
)(run_command)
app.command(
    name="cost",
    help="Aggregate token usage from .eden/sessions/ session JSONLs.",
)(cost_command)
app.command(
    name="clean",
    help="Delete stale .eden/{logs,sessions,worktrees,isolated} artifacts.",
)(clean_command)
app.command(
    name="replay",
    help="Pretty-print a captured session JSONL transcript.",
)(replay_command)


@app.command(name="version", help="Print the eden version and exit.")
def version_command() -> None:
    typer.echo(__version__)
