"""Agent Protocol — minimal in 3a (build_command + parse_stream)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from eden.agents._context import IterationContext
from eden.streaming import StreamEvent


@runtime_checkable
class Agent(Protocol):
    # Declared as read-only properties so that frozen dataclasses (e.g.
    # _ClaudeCodeAgent) satisfy the protocol without mypy raising
    # "expected settable variable, got read-only attribute".
    @property
    def name(self) -> str: ...

    @property
    def model(self) -> str: ...

    def build_command(self, ctx: IterationContext) -> list[str]: ...

    def parse_stream(self, line: str) -> StreamEvent | None: ...
