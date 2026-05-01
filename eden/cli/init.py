"""`eden init` — scaffold a `.eden/` directory in the current repo.

Phase 1 ships a stub that reports "not implemented." The full interactive
scaffolder lands in phase 6 (CLI & templates).
"""

from __future__ import annotations

import typer
from rich.console import Console

console = Console(stderr=True)


def init_command() -> None:
    console.print(
        "[red]eden init is not implemented yet.[/red] "
        "Full scaffolder lands in phase 6 of the rewrite.",
    )
    raise typer.Exit(code=1)
