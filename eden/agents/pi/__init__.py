"""pi CLI agent."""

from __future__ import annotations

from collections.abc import Mapping

from eden.agents._protocol import Agent
from eden.agents.cli import cli_agent
from eden.agents.pi._stream import parse_line as _parse_line
from eden.streaming import StreamEvent

_NAME = "pi"


def _parse_stream(line: str) -> StreamEvent | None:
    return _parse_line(line, agent_name=_NAME, iteration=0)


def pi(
    model: str = "pi-3.5",
    *,
    env: Mapping[str, str] | None = None,
    extra_args: tuple[str, ...] = (),
) -> Agent:
    """pi CLI agent. Assumes `pi` binary is on PATH.

    Default `model` ("pi-3.5") is illustrative — override via the positional
    `model` argument or supply your own `extra_args` for binary-specific flags.

    The agent's ``parse_stream`` decodes pi JSONL events (``message_update`` /
    ``text_delta``, ``tool_execution_start`` for known tools (``Bash``,
    ``WebSearch``, ``WebFetch``, ``Agent``), ``agent_end``, ``agent_error`` /
    ``error``) so live display and file logs see structured text / tool_call
    events instead of one-line-per-token noise.
    """
    return cli_agent(
        name=_NAME,
        model=model,
        binary=_NAME,
        parse_stream=_parse_stream,
        env=env,
        extra_args=extra_args,
    )


__all__ = ["pi"]
