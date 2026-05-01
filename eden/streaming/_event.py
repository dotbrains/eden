"""StreamEvent: discriminated-union event emitted from the orchestrator."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass(frozen=True)
class StreamEvent:
    """Phase 3a kinds: 'text', 'idle_warning'. Phase 3b adds 'tool_call'."""

    type: Literal["text", "idle_warning"]
    agent_name: str
    iteration: int
    timestamp: datetime
    text: str | None = None
    minutes_idle: int | None = None
