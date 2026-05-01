"""StreamEvent: discriminated-union event emitted from the orchestrator."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass(frozen=True)
class StreamEvent:
    """Discriminated-union event from the orchestrator.

    Phase 3a kinds: ``"text"`` (carries ``text``) and ``"idle_warning"`` (carries
    ``minutes_idle``). Phase 3b adds ``"tool_call"``.
    """

    type: Literal["text", "idle_warning"]
    agent_name: str
    iteration: int
    timestamp: datetime
    text: str | None = None
    minutes_idle: int | None = None

    def __post_init__(self) -> None:
        if self.type == "text" and self.text is None:
            raise ValueError('StreamEvent type="text" requires text to be non-None')
        if self.type == "idle_warning" and self.minutes_idle is None:
            raise ValueError('StreamEvent type="idle_warning" requires minutes_idle to be non-None')
