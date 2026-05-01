"""Agent Protocol — minimal in 3a (build_command + parse_stream)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from eden.agents._context import IterationContext
from eden.streaming import StreamEvent


@runtime_checkable
class Agent(Protocol):
    name: str
    model: str

    def build_command(self, ctx: IterationContext) -> list[str]: ...

    def parse_stream(self, line: str) -> StreamEvent | None: ...
