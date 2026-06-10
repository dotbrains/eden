"""_ClaudeCodeAgent dataclass — implements the Agent Protocol structurally."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from eden.agents._context import IterationContext
from eden.agents.claude_code._argv import build_argv
from eden.agents.claude_code._stream import parse_line
from eden.streaming import StreamEvent

if TYPE_CHECKING:
    from eden.session._protocol import SessionStorage


@dataclass(frozen=True)
class _ClaudeCodeAgent:
    name: str
    model: str
    captures_sessions: bool
    _effort: Literal["low", "medium", "high"] | None = None
    _env: Mapping[str, str] = field(default_factory=dict)
    _extra_args: tuple[str, ...] = ()
    _dangerously_skip_permissions: bool = False
    _session_storage: SessionStorage | None = None
    flox_env: str | Path | None = None

    @property
    def session_storage(self) -> SessionStorage | None:
        """Per-agent session capture hook (ADR-0012-style).

        Returns ``None`` when ``capture_sessions=False`` was passed to
        :func:`claude_code`. Otherwise returns a :class:`ClaudeSessionStorage`
        configured for the default ``~/.claude/projects`` location.
        """
        return self._session_storage

    def build_command(self, ctx: IterationContext) -> list[str]:
        return build_argv(
            model=self.model,
            effort=self._effort,
            extra_args=self._extra_args,
            resume_session=ctx.resume_session,
            fork_session=ctx.fork_session,
            dangerously_skip_permissions=self._dangerously_skip_permissions,
        )

    def stdin_content(self, ctx: IterationContext) -> str | None:
        """Deliver the prompt via stdin to dodge the Linux 128 KB execve limit."""
        return ctx.prompt

    def build_interactive_command(self, ctx: IterationContext) -> list[str]:
        """Build argv for an interactive (TTY) Claude Code session.

        No ``--print``, no ``-p -``, no stream-json — claude's default TUI is
        what the user sees. The optional prompt is appended as a positional
        seed argument; an empty prompt drops it entirely.
        """
        argv: list[str] = ["claude", "--model", self.model]
        if self._effort is not None:
            argv.extend(["--thinking-effort", self._effort])
        if self._dangerously_skip_permissions:
            argv.append("--dangerously-skip-permissions")
        argv.extend(self._extra_args)
        if ctx.prompt:
            argv.append(ctx.prompt)
        return argv

    def parse_stream(self, line: str) -> StreamEvent | None:
        return parse_line(line, agent_name=self.name, iteration=0)
