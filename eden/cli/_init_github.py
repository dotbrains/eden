"""GitHub setup helpers for ``eden init``."""

from __future__ import annotations

import subprocess

import typer
from rich.console import Console

_console = Console(stderr=True)


def create_github_label() -> None:
    argv = [
        "gh",
        "label",
        "create",
        "eden",
        "--description",
        "Ready for Eden agents",
        "--color",
        "5319E7",
        "--force",
    ]
    _console.print(f"[cyan]→ {' '.join(argv)}[/cyan]")
    proc = subprocess.run(argv, check=False)
    if proc.returncode != 0:
        raise typer.Exit(code=proc.returncode)
    _console.print("[green]created or updated GitHub label eden[/green]")
