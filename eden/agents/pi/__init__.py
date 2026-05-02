"""pi CLI agent."""

from __future__ import annotations

from collections.abc import Mapping

from eden.agents._protocol import Agent
from eden.agents.cli import cli_agent


def pi(
    model: str = "pi-3.5",
    *,
    env: Mapping[str, str] | None = None,
    extra_args: tuple[str, ...] = (),
) -> Agent:
    """pi CLI agent. Assumes `pi` binary is on PATH.

    Default `model` ("pi-3.5") is illustrative — override via the positional
    `model` argument or supply your own `extra_args` for binary-specific flags.
    """
    return cli_agent(
        name="pi",
        model=model,
        binary="pi",
        env=env,
        extra_args=extra_args,
    )


__all__ = ["pi"]
