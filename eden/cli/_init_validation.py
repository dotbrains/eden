"""Option validation for ``eden init``."""

from __future__ import annotations

import typer

from eden.cli._init_templates import (
    TEMPLATES_REQUIRING_BACKLOG,
    VALID_AGENTS,
    VALID_BACKLOGS,
    VALID_SANDBOXES,
    VALID_TEMPLATES,
)


def validate_init_options(
    *,
    sandbox: str,
    agent: str,
    template: str,
    backlog: str | None,
) -> None:
    if sandbox not in VALID_SANDBOXES:
        raise typer.BadParameter(
            f"sandbox must be one of {list(VALID_SANDBOXES)}, got {sandbox!r}",
        )
    if agent not in VALID_AGENTS:
        raise typer.BadParameter(
            f"agent must be one of {list(VALID_AGENTS)}, got {agent!r}",
        )
    if template not in VALID_TEMPLATES:
        raise typer.BadParameter(
            f"template must be one of {list(VALID_TEMPLATES)}, got {template!r}",
        )
    if template in TEMPLATES_REQUIRING_BACKLOG and backlog not in VALID_BACKLOGS:
        raise typer.BadParameter(
            f"backlog must be one of {list(VALID_BACKLOGS)}, got {backlog!r}",
        )


__all__ = ["validate_init_options"]
