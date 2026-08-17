"""``eden routine`` — save, list, inspect, and re-run named ``eden run`` configs.

A routine is a saved bundle of ``eden run`` flags (sandbox, agent, model,
template, backlog, timeouts) under ``.eden/routines/<name>.json``, invocable
by name instead of re-typing the full flag set every time. Routine files are
tracked in git like the rest of a scaffolded ``.eden/`` directory, so
history/versioning comes from git itself — see
``docs/adr/0018-named-routines.md``.
"""

from __future__ import annotations

import typer

from eden.cli.routine._inspect import list_command, remove_command, show_command
from eden.cli.routine._run import run_command
from eden.cli.routine._save import save_command


def make_routine_app() -> typer.Typer:
    """Build the ``eden routine`` Typer sub-app."""
    app = typer.Typer(
        name="routine",
        help="Save, list, inspect, and re-run named eden run configs.",
        no_args_is_help=True,
        add_completion=False,
    )
    app.command(name="save", help="Save flags as a named routine.")(save_command)
    app.command(name="list", help="List saved routines.")(list_command)
    app.command(name="show", help="Print a saved routine's configuration.")(show_command)
    app.command(name="remove", help="Delete a saved routine.")(remove_command)
    app.command(name="run", help="Run a saved routine via eden.run().")(run_command)
    return app


__all__ = ["make_routine_app"]
