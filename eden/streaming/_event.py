"""StreamEvent: discriminated-union event emitted from the orchestrator."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from eden._types import Usage


@dataclass(frozen=True)
class StreamEvent:
    """Discriminated-union event from the orchestrator.

    Phase 3a kinds: ``"text"`` (carries ``text``) and ``"idle_warning"`` (carries
    ``minutes_idle``). Phase 3b adds ``"tool_call"`` (carries ``tool_name`` and
    ``tool_input``), ``"usage"`` (carries ``usage`` and ``session_id``), and
    ``"session_id"`` (carries ``session_id`` standalone — emitted by agents
    whose stream announces the session before any usage data is available,
    e.g. codex's ``thread.started``).

    ``"raw"`` (carries ``text``) is the literal, unparsed stdout line as the
    agent emitted it, surfaced only when ``Logging(verbose=True)`` so external
    observability systems can see the bytes a parser would otherwise discard
    (e.g. the JSON envelope behind a ``claude --output-format stream-json``
    line). Mirrors sandcastle's ``{ type: "raw" }`` verbose event (v0.10.0).
    """

    type: Literal["text", "idle_warning", "tool_call", "usage", "session_id", "raw"]
    agent_name: str
    iteration: int
    timestamp: datetime
    text: str | None = None
    minutes_idle: int | None = None
    tool_name: str | None = None
    tool_input: dict[str, object] | None = None
    usage: Usage | None = None
    session_id: str | None = None

    def __post_init__(self) -> None:
        if self.type == "text" and self.text is None:
            raise ValueError('StreamEvent type="text" requires text to be non-None')
        if self.type == "idle_warning" and self.minutes_idle is None:
            raise ValueError('StreamEvent type="idle_warning" requires minutes_idle to be non-None')
        if self.type == "tool_call" and self.tool_name is None:
            raise ValueError('StreamEvent type="tool_call" requires tool_name to be non-None')
        if self.type == "usage" and self.usage is None:
            raise ValueError('StreamEvent type="usage" requires usage to be non-None')
        if self.type == "session_id" and self.session_id is None:
            raise ValueError('StreamEvent type="session_id" requires session_id to be non-None')
        if self.type == "raw" and self.text is None:
            raise ValueError('StreamEvent type="raw" requires text to be non-None')
