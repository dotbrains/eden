"""Agent environment helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from eden.agents._protocol import Agent


def agent_env(agent: Agent) -> Mapping[str, str]:
    """Return environment additions declared by built-in agent factories."""
    raw = getattr(agent, "_env", {})
    if isinstance(raw, Mapping):
        return cast(Mapping[str, str], raw)
    return {}


__all__ = ["agent_env"]
