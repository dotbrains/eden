"""Cursor (cursor-agent CLI) agent."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from eden.agents._argv_guards import assert_prompt_fits_argv
from eden.agents._context import IterationContext
from eden.agents._protocol import Agent
from eden.agents.cursor._argv import build_argv
from eden.agents.cursor._stream import parse_line
from eden.streaming import StreamEvent

_NAME = "cursor"


@dataclass(frozen=True)
class _CursorAgent:
    name: str
    model: str
    captures_sessions: bool
    _env: Mapping[str, str] = field(default_factory=dict)
    _extra_args: tuple[str, ...] = ()
    _force: bool = False
    flox_env: str | Path | None = None

    def build_command(self, ctx: IterationContext) -> list[str]:
        assert_prompt_fits_argv(prompt=ctx.prompt, agent_name=self.name)
        return build_argv(
            model=self.model,
            extra_args=self._extra_args,
            prompt=ctx.prompt,
            force=self._force,
        )

    def parse_stream(self, line: str) -> StreamEvent | None:
        return parse_line(line, agent_name=self.name, iteration=0)


def cursor(
    model: str = "claude-sonnet-4-6",
    *,
    name: str = _NAME,
    env: Mapping[str, str] | None = None,
    force: bool = False,
    extra_args: tuple[str, ...] = (),
    flox_env: str | Path | None = None,
) -> Agent:
    """Cursor CLI agent. Assumes the ``agent`` binary (Cursor's CLI) is on PATH.

    Builds the invocation::

        agent --print --output-format stream-json --model <model>
              [--force] [extra_args ...] <prompt>

    The prompt is delivered positionally; ``InvalidOptions`` is raised
    pre-flight if it would overflow the ~120 KB Linux execve argv limit.
    Cursor does not currently support session capture (``captures_sessions``
    is always ``False``); resume is not available.

    Args:
        model: Cursor model id (default ``"claude-sonnet-4-6"`` is
            illustrative — supply whatever identifier your cursor-agent
            install accepts).
        name: Agent identifier (default ``"cursor"``).
        env: Per-agent environment additions (merged by the orchestrator).
        force: When ``True``, appends ``--force`` so cursor does not block
            on per-tool permission prompts. Cursor's equivalent of Claude's
            ``dangerously_skip_permissions``.
        extra_args: Inserted between the standard flags and the prompt.
        flox_env: Optional path to a directory containing a Flox env
            (``.flox/env/manifest.toml``). When set, the orchestrator runs
            cursor inside it via ``flox activate -d <dir> -- <argv>``. Enforced
            when present: a missing manifest or ``flox`` binary raises
            ``FloxEnvError`` (set ``EDEN_ALLOW_NO_FLOX=1`` to skip activation).

    The agent's ``parse_stream`` handles cursor's ``tool_call`` events
    plus the Claude-compatible ``assistant`` / ``result`` event shapes.
    """
    return _CursorAgent(
        name=name,
        model=model,
        captures_sessions=False,
        _env=dict(env) if env is not None else {},
        _extra_args=tuple(extra_args),
        _force=force,
        flox_env=flox_env,
    )


__all__ = ["cursor"]
