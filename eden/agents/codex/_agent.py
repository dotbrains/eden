"""_CodexAgent dataclass — implements the Agent Protocol structurally."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from eden.agents._context import IterationContext
from eden.agents.codex._argv import ApprovalsReviewer, Effort, build_argv
from eden.agents.codex._stream import parse_line
from eden.streaming import StreamEvent

if TYPE_CHECKING:
    from eden.session._protocol import SessionStorage


@dataclass(frozen=True)
class _CodexAgent:
    name: str
    model: str
    captures_sessions: bool
    _effort: Effort | None = None
    _env: Mapping[str, str] = field(default_factory=dict)
    _extra_args: tuple[str, ...] = ()
    _dangerously_bypass_approvals_and_sandbox: bool = True
    _approvals_reviewer: ApprovalsReviewer | None = None
    _session_storage: SessionStorage | None = None
    flox_env: str | Path | None = None

    @property
    def session_storage(self) -> SessionStorage | None:
        """Per-agent session capture hook (ADR-0012-style).

        Returns ``None`` when ``capture_sessions=False`` was passed to
        :func:`codex`. Otherwise returns a :class:`CodexSessionStorage`
        configured for the default ``~/.codex/sessions`` location.
        """
        return self._session_storage

    def build_command(self, ctx: IterationContext) -> list[str]:
        return build_argv(
            model=self.model,
            effort=self._effort,
            extra_args=self._extra_args,
            resume_session=ctx.resume_session,
            fork_session=ctx.fork_session,
            dangerously_bypass_approvals_and_sandbox=(
                self._dangerously_bypass_approvals_and_sandbox
            ),
            approvals_reviewer=self._approvals_reviewer,
        )

    def stdin_content(self, ctx: IterationContext) -> str | None:
        """Deliver the prompt via stdin to mirror codex's expected invocation."""
        return ctx.prompt

    def parse_stream(self, line: str) -> StreamEvent | None:
        return parse_line(line, agent_name=self.name, iteration=0)
