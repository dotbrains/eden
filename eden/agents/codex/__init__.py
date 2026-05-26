"""OpenAI Codex CLI agent."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from eden.agents._context import IterationContext
from eden.agents._protocol import Agent
from eden.agents.cli import cli_agent
from eden.agents.codex._stream import parse_line as _parse_line
from eden.streaming import StreamEvent

Effort = Literal["low", "medium", "high", "xhigh"]

_NAME = "codex"


def _parse_stream(line: str) -> StreamEvent | None:
    return _parse_line(line, agent_name=_NAME, iteration=0)


def codex(
    model: str = "gpt-5",
    *,
    effort: Effort | None = None,
    env: Mapping[str, str] | None = None,
    extra_args: tuple[str, ...] = (),
) -> Agent:
    """OpenAI Codex CLI agent. Assumes `codex` binary is on PATH.

    Args:
        model: Default ``"gpt-5"`` is illustrative — override per call site.
        effort: Optional reasoning-effort level. When set, threads
            ``-c model_reasoning_effort="<level>"`` into the codex invocation.
            One of ``"low"``, ``"medium"``, ``"high"``, ``"xhigh"``.
        env: Per-agent environment additions (merged by the orchestrator).
        extra_args: Inserted between the effort override (if any) and the prompt.

    The agent's ``parse_stream`` decodes codex JSONL events (``thread.started``,
    ``item.completed`` / ``agent_message``, ``item.started`` /
    ``command_execution``, ``error``) so live display and file logs see
    structured text / tool_call / session_id / error events instead of
    one-line-per-token noise.
    """
    if effort is None:
        return cli_agent(
            name=_NAME,
            model=model,
            binary=_NAME,
            parse_stream=_parse_stream,
            env=env,
            extra_args=extra_args,
        )

    def _build(ctx: IterationContext) -> list[str]:
        argv: list[str] = [
            _NAME,
            "-c",
            f'model_reasoning_effort="{effort}"',
        ]
        argv.extend(extra_args)
        argv.append(ctx.prompt)
        return argv

    return cli_agent(
        name=_NAME,
        model=model,
        binary=_NAME,
        build_argv=_build,
        parse_stream=_parse_stream,
        env=env,
        extra_args=extra_args,
    )


__all__ = ["codex"]
