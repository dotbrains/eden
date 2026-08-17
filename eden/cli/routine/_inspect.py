"""`eden routine list` / `show` / `remove` — manage saved routine configs."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from eden.cli.routine._store import delete_routine, list_routines, load_routine

console = Console(stderr=True)


def list_command(
    cwd: Path | None = typer.Option(None, "--cwd", help="Repo to list routines in"),  # noqa: B008
) -> None:
    """List routines saved under .eden/routines/."""
    repo = (cwd or Path.cwd()).resolve()
    names = list_routines(repo)
    if not names:
        console.print(f"[yellow]no routines saved in {repo / '.eden' / 'routines'}[/yellow]")
        raise typer.Exit(code=0)

    table = Table(show_header=True, header_style="bold cyan")
    for column in ("name", "sandbox", "agent", "model", "template", "backlog"):
        table.add_column(column)
    for name in names:
        config = load_routine(repo, name)
        table.add_row(
            name, config.sandbox, config.agent, config.model, config.template, config.backlog
        )
    console.print(table)


def show_command(
    name: str = typer.Argument(..., help="Routine name"),
    cwd: Path | None = typer.Option(None, "--cwd", help="Repo to look up the routine in"),  # noqa: B008
) -> None:
    """Print a saved routine's full configuration."""
    repo = (cwd or Path.cwd()).resolve()
    try:
        config = load_routine(repo, name)
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    for key, value in asdict(config).items():
        typer.echo(f"{key}: {value}")


def remove_command(
    name: str = typer.Argument(..., help="Routine name"),
    cwd: Path | None = typer.Option(None, "--cwd", help="Repo to remove the routine from"),  # noqa: B008
) -> None:
    """Delete a saved routine."""
    repo = (cwd or Path.cwd()).resolve()
    try:
        removed = delete_routine(repo, name)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if not removed:
        console.print(f"[yellow]no routine named {name!r}[/yellow]")
        raise typer.Exit(code=1)
    console.print(f"[green]removed routine {name!r}[/green]")
