"""opencode CLI agent."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from eden.agents._context import IterationContext
from eden.agents._protocol import Agent
from eden.agents.opencode._argv import build_argv
from eden.agents.opencode._stream import parse_line
from eden.streaming import StreamEvent


@dataclass(frozen=True)
class _OpenCodeAgent:
    name: str
    model: str
    captures_sessions: bool
    _variant: str | None = None
    _agent_mode: str | None = None
    _env: Mapping[str, str] = field(default_factory=dict)
    _extra_args: tuple[str, ...] = ()
    _dangerously_skip_permissions: bool = False
    flox_env: str | Path | None = None

    def build_command(self, ctx: IterationContext) -> list[str]:
        return build_argv(
            model=self.model,
            variant=self._variant,
            agent=self._agent_mode,
            extra_args=self._extra_args,
            prompt=ctx.prompt,
            dangerously_skip_permissions=self._dangerously_skip_permissions,
        )

    def parse_stream(self, line: str) -> StreamEvent | None:
        return parse_line(line, agent_name=self.name, iteration=0)


def opencode(
    model: str = "claude-opus-4",
    *,
    name: str = "opencode",
    variant: str | None = None,
    agent: str | None = None,
    env: Mapping[str, str] | None = None,
    dangerously_skip_permissions: bool = False,
    extra_args: tuple[str, ...] = (),
    flox_env: str | Path | None = None,
) -> Agent:
    """opencode CLI agent (sst/opencode). Assumes ``opencode`` binary is on PATH.

    Builds the invocation ``opencode run --format json --model <model>
    [--variant <v>] [--agent <name>] [--dangerously-skip-permissions]
    [extra_args ...] <prompt>``. ``--format json`` is always present so the
    bundled :mod:`eden.agents.opencode._stream` parser receives structured
    events.

    Args:
        model: Model identifier passed via ``--model``. Default
            ``"claude-opus-4"`` is illustrative — opencode supports multiple
            providers; override per call site.
        name: Agent identifier (default ``"opencode"``).
        variant: Optional reasoning-effort variant passed via ``--variant``
            (e.g. ``"high"``, ``"max"``, ``"low"``, ``"minimal"``).
        agent: Optional named agent mode passed via ``--agent`` (e.g.
            ``"build"`` / ``"plan"``); opencode selects a different
            built-in agent persona per mode.
        env: Per-agent environment additions (merged by the orchestrator).
        dangerously_skip_permissions: When ``True``, appends
            ``--dangerously-skip-permissions`` so opencode does not block
            on per-tool permission prompts. Safe inside isolated sandboxes;
            think twice before enabling for ``no_sandbox()``.
        extra_args: Inserted between the flag block and the prompt.
        flox_env: Optional path to a directory containing a Flox env
            (``.flox/env/manifest.toml``). When set, the orchestrator runs
            opencode inside it via ``flox activate -d <dir> -- <argv>``.
            Enforced when present: a missing manifest or ``flox`` binary raises
            ``FloxEnvError`` (set ``EDEN_ALLOW_NO_FLOX=1`` to skip activation).

    The agent's ``parse_stream`` decodes opencode JSONL events (``step_start``
    → ``session_id``, ``text`` → ``text``, ``tool_use`` → ``tool_call``,
    ``error`` → ``text``).
    """
    return _OpenCodeAgent(
        name=name,
        model=model,
        captures_sessions=False,
        _variant=variant,
        _agent_mode=agent,
        _env=dict(env) if env is not None else {},
        _extra_args=tuple(extra_args),
        _dangerously_skip_permissions=dangerously_skip_permissions,
        flox_env=flox_env,
    )


__all__ = ["opencode"]
