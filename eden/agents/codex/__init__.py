"""OpenAI Codex CLI agent."""

from __future__ import annotations

from collections.abc import Mapping

from eden.agents._protocol import Agent
from eden.agents.cli import cli_agent


def codex(
    model: str = "gpt-5",
    *,
    env: Mapping[str, str] | None = None,
    extra_args: tuple[str, ...] = (),
) -> Agent:
    """OpenAI Codex CLI agent. Assumes `codex` binary is on PATH.

    Default `model` ("gpt-5") is illustrative — Codex CLI may name models
    differently. Override via the positional `model` argument or supply your
    own `extra_args` for binary-specific flags.
    """
    return cli_agent(
        name="codex",
        model=model,
        binary="codex",
        env=env,
        extra_args=extra_args,
    )


__all__ = ["codex"]
