"""GitHub Copilot CLI agent."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from eden.agents._argv_guards import assert_prompt_fits_argv
from eden.agents._context import IterationContext
from eden.agents._protocol import Agent
from eden.agents.copilot._argv import Effort, build_argv
from eden.agents.copilot._stream import parse_line
from eden.streaming import StreamEvent

_NAME = "copilot"


@dataclass(frozen=True)
class _CopilotAgent:
    name: str
    model: str
    captures_sessions: bool
    _effort: Effort | None = None
    _env: Mapping[str, str] = field(default_factory=dict)
    _extra_args: tuple[str, ...] = ()
    _allow_all_tools: bool = False
    flox_env: str | Path | None = None

    def build_command(self, ctx: IterationContext) -> list[str]:
        assert_prompt_fits_argv(prompt=ctx.prompt, agent_name=self.name)
        return build_argv(
            model=self.model,
            effort=self._effort,
            extra_args=self._extra_args,
            prompt=ctx.prompt,
            allow_all_tools=self._allow_all_tools,
        )

    def parse_stream(self, line: str) -> StreamEvent | None:
        return parse_line(line, agent_name=self.name, iteration=0)


def copilot(
    model: str = "claude-sonnet-4",
    *,
    name: str = _NAME,
    effort: Effort | None = None,
    env: Mapping[str, str] | None = None,
    allow_all_tools: bool = False,
    extra_args: tuple[str, ...] = (),
    flox_env: str | Path | None = None,
) -> Agent:
    """GitHub Copilot CLI agent. Assumes the ``copilot`` binary is on PATH.

    Builds the invocation::

        copilot -p <prompt> --output-format json --model <model>
                [--allow-all-tools] [--effort <level>] [extra_args ...]

    The prompt is passed via ``-p`` (still argv); ``InvalidOptions`` is
    raised pre-flight if it would overflow the ~120 KB Linux execve argv
    limit. Copilot does not currently support session capture
    (``captures_sessions`` is always ``False``); resume is not available.

    Args:
        model: Copilot model id. Default ``"claude-sonnet-4"`` is
            illustrative — supply whatever identifier your Copilot CLI
            accepts.
        name: Agent identifier (default ``"copilot"``).
        effort: Optional reasoning-effort level (``"low"``, ``"medium"``,
            ``"high"``). When set, threads ``--effort <level>`` into the
            invocation.
        env: Per-agent environment additions (merged by the orchestrator).
        allow_all_tools: When ``True``, appends ``--allow-all-tools`` so
            Copilot does not block on per-tool permission prompts.
            Copilot's equivalent of Claude's
            ``dangerously_skip_permissions``.
        extra_args: Appended after the standard flags.
        flox_env: Optional path to a directory containing a Flox env
            (``.flox/env/manifest.toml``). When set, the orchestrator runs
            copilot inside it via ``flox activate -d <dir> -- <argv>``.
            Enforced when present: a missing manifest or ``flox`` binary raises
            ``FloxEnvError`` (set ``EDEN_ALLOW_NO_FLOX=1`` to skip activation).

    The agent's ``parse_stream`` decodes Copilot JSONL events
    (``assistant.message_delta`` → ``text``, ``tool.execution_start`` →
    ``tool_call`` (Bash on ``"bash"`` normalisation), ``result`` →
    ``session_id``, ``error`` / ``agent_error`` → ``text``).
    """
    return _CopilotAgent(
        name=name,
        model=model,
        captures_sessions=False,
        _effort=effort,
        _env=dict(env) if env is not None else {},
        _extra_args=tuple(extra_args),
        _allow_all_tools=allow_all_tools,
        flox_env=flox_env,
    )


__all__ = ["copilot"]
