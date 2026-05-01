"""Agent factories + Protocol."""

from __future__ import annotations

from eden.agents._context import IterationContext
from eden.agents._protocol import Agent
from eden.agents.claude_code import claude_code
from eden.agents.simulated import simulated_agent

__all__ = ["Agent", "IterationContext", "claude_code", "simulated_agent"]
