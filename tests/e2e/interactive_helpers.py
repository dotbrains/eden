"""Shared helpers for interactive e2e tests."""

from __future__ import annotations

import sys

import eden
from eden.agents._context import IterationContext
from eden.agents.cli import cli_agent


def exit_zero_agent() -> eden.Agent:
    """Build an agent whose argv exits 0 immediately."""

    def _build(_ctx: IterationContext) -> list[str]:
        return [sys.executable, "-c", "import sys; sys.exit(0)"]

    return cli_agent(name="probe", model="x", binary="ignored", build_argv=_build)


def exit_n_agent(n: int) -> eden.Agent:
    def _build(_ctx: IterationContext) -> list[str]:
        return [sys.executable, "-c", f"import sys; sys.exit({n})"]

    return cli_agent(name="probe", model="x", binary="ignored", build_argv=_build)
