"""`eden routine run` — execute a previously saved routine."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from eden.cli._templates._backlog import get_backlog_manager
from eden.cli._templates.simple_loop import render_simple_loop_prompt
from eden.cli.routine._store import RoutineConfig, load_routine
from eden.cli.run import (
    _VALID_AGENTS,
    _VALID_BACKLOGS,
    _VALID_SANDBOXES,
    _VALID_TEMPLATES,
    _build_agent,
    _build_sandbox,
    _completion_summary,
)
from eden.orchestrator import run as eden_run

console = Console(stderr=True)


def _execute(config: RoutineConfig, *, name: str, cwd: Path | None) -> None:
    # Re-checked at run time (not just at save time) in case a routine file
    # was hand-edited after saving, or written by an older/newer eden whose
    # supported values have since changed.
    sandbox, agent, backlog, template = (
        config.sandbox,
        config.agent,
        config.backlog,
        config.template,
    )
    if sandbox not in _VALID_SANDBOXES:
        raise typer.BadParameter(f"routine {name!r} has invalid sandbox {sandbox!r}")
    if agent not in _VALID_AGENTS:
        raise typer.BadParameter(f"routine {name!r} has invalid agent {agent!r}")
    if backlog not in _VALID_BACKLOGS:
        raise typer.BadParameter(f"routine {name!r} has invalid backlog {backlog!r}")
    if template not in _VALID_TEMPLATES:
        raise typer.BadParameter(f"routine {name!r} has invalid template {template!r}")

    agent_factory = _build_agent(agent, config.model)
    sandbox_provider = _build_sandbox(sandbox, config.image_name)
    backlog_manager = get_backlog_manager(backlog)
    prompt = render_simple_loop_prompt(backlog_manager)

    console.print(
        f"[cyan]eden routine run[/cyan] {name} sandbox={config.sandbox} "
        f"agent={config.agent} model={config.model} backlog={config.backlog}"
    )

    result = eden_run(
        agent=agent_factory,
        sandbox=sandbox_provider,
        prompt=prompt,
        max_iterations=config.max_iterations,
        idle_timeout=config.idle_timeout,
        completion_timeout=config.completion_timeout,
        cwd=cwd,
    )

    typer.echo(
        _completion_summary(
            completion_signal=result.completion_signal,
            iterations=len(result.iterations),
        )
    )
    typer.echo(f"Completion: {result.completion_signal or '(not reached)'}")
    typer.echo(f"Iterations: {len(result.iterations)}")
    typer.echo(f"Branch:     {result.branch}")


def run_command(
    name: str = typer.Argument(..., help="Routine name"),
    cwd: Path | None = typer.Option(None, "--cwd", help="Repo to run in"),  # noqa: B008
) -> None:
    """Run a previously saved routine via ``eden.run()``."""
    repo = (cwd or Path.cwd()).resolve()
    try:
        config = load_routine(repo, name)
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    _execute(config, name=name, cwd=cwd)
