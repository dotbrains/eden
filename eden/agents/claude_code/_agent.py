"""_ClaudeCodeAgent dataclass — implements the Agent Protocol structurally."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

from eden.agents._context import IterationContext
from eden.agents.claude_code._argv import build_argv
from eden.agents.claude_code._stream import parse_line
from eden.streaming import StreamEvent


@dataclass(frozen=True)
class _ClaudeCodeAgent:
    name: str
    model: str
    captures_sessions: bool
    _effort: Literal["low", "medium", "high"] | None = None
    _env: Mapping[str, str] = field(default_factory=dict)
    _extra_args: tuple[str, ...] = ()

    def build_command(self, ctx: IterationContext) -> list[str]:
        return build_argv(
            model=self.model,
            effort=self._effort,
            prompt=ctx.prompt,
            extra_args=self._extra_args,
        )

    def parse_stream(self, line: str) -> StreamEvent | None:
        return parse_line(line, agent_name=self.name, iteration=0)
