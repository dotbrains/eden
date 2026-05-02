"""opencode CLI agent."""

from __future__ import annotations

from collections.abc import Mapping

from eden.agents._protocol import Agent
from eden.agents.cli import cli_agent


def opencode(
    model: str = "claude-opus-4",
    *,
    env: Mapping[str, str] | None = None,
    extra_args: tuple[str, ...] = (),
) -> Agent:
    """opencode CLI agent (sst/opencode). Assumes `opencode` binary is on PATH.

    Default `model` ("claude-opus-4") is illustrative — opencode supports
    multiple model providers; override via the positional `model` argument or
    supply your own `extra_args`.
    """
    return cli_agent(
        name="opencode",
        model=model,
        binary="opencode",
        env=env,
        extra_args=extra_args,
    )


__all__ = ["opencode"]
