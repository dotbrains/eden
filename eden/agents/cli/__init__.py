"""Generic CLI-tool Agent factory.

Wraps any line-streaming CLI binary into an Agent that satisfies Phase 3a's
`Agent` Protocol. Use cli_agent directly for arbitrary binaries; the
codex/opencode/pi sub-packages are 5-line wrappers over cli_agent with
sensible defaults.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from eden.agents._argv_guards import assert_prompt_fits_argv
from eden.agents._context import IterationContext
from eden.agents._protocol import Agent
from eden.streaming import StreamEvent

_BuildArgv = Callable[[IterationContext], list[str]]
_ParseStream = Callable[[str], StreamEvent | None]


@dataclass(frozen=True)
class _CliAgent:
    name: str
    model: str
    captures_sessions: bool
    _binary: str
    _build_argv: _BuildArgv | None = None
    _parse_stream: _ParseStream | None = None
    _env: Mapping[str, str] = field(default_factory=dict)
    _extra_args: tuple[str, ...] = ()
    flox_env: str | Path | None = None

    def build_command(self, ctx: IterationContext) -> list[str]:
        if self._build_argv is not None:
            return self._build_argv(ctx)
        assert_prompt_fits_argv(prompt=ctx.prompt, agent_name=self.name)
        return [self._binary, *self._extra_args, ctx.prompt]

    def parse_stream(self, line: str) -> StreamEvent | None:
        if self._parse_stream is not None:
            return self._parse_stream(line)
        return None


def cli_agent(
    *,
    name: str,
    model: str,
    binary: str,
    build_argv: _BuildArgv | None = None,
    parse_stream: _ParseStream | None = None,
    captures_sessions: bool = False,
    env: Mapping[str, str] | None = None,
    extra_args: tuple[str, ...] = (),
    flox_env: str | Path | None = None,
) -> Agent:
    """Build an Agent for any line-streaming CLI tool.

    Args:
        name: Agent identifier (used in StreamEvent.agent_name).
        model: Model identifier (informational; threaded to the CLI's argv
            if `build_argv` references it).
        binary: Executable name; resolved via $PATH at subprocess-spawn time.
        build_argv: Optional override; default produces
            ``[binary, *extra_args, ctx.prompt]``.
        parse_stream: Optional override; default returns ``None`` (orchestrator
            fallback emits a `text` StreamEvent per line).
        captures_sessions: When ``True``, orchestrator post-processes session
            JSONL into ``.eden/sessions/...`` (requires the agent to write to
            ``~/.claude/projects/<slug>/<id>.jsonl``). Default ``False``.
        env: Per-agent environment additions (merged by the orchestrator).
        extra_args: Default-build_argv inserts these between binary and prompt.
        flox_env: Optional path to a directory containing a Flox env
            (``.flox/env/manifest.toml``). When set, the orchestrator runs the
            CLI inside it via ``flox activate -d <dir> -- <argv>``. Enforced
            when present: a missing manifest or ``flox`` binary raises
            ``FloxEnvError`` (set ``EDEN_ALLOW_NO_FLOX=1`` to skip activation).
    """
    return _CliAgent(
        name=name,
        model=model,
        captures_sessions=captures_sessions,
        _binary=binary,
        _build_argv=build_argv,
        _parse_stream=parse_stream,
        _env=dict(env) if env is not None else {},
        _extra_args=tuple(extra_args),
        flox_env=flox_env,
    )


__all__ = ["cli_agent"]
