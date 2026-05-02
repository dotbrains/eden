"""Agent factories + Protocol."""

from __future__ import annotations

from eden.agents._context import IterationContext
from eden.agents._protocol import Agent
from eden.agents.claude_code import claude_code
from eden.agents.cli import cli_agent
from eden.agents.codex import codex
from eden.agents.opencode import opencode
from eden.agents.pi import pi
from eden.agents.simulated import simulated_agent

__all__ = [
    "Agent",
    "IterationContext",
    "claude_code",
    "cli_agent",
    "codex",
    "opencode",
    "pi",
    "simulated_agent",
]
