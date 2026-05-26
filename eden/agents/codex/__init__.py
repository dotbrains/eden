"""OpenAI Codex CLI agent."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from eden.agents._context import IterationContext
from eden.agents._protocol import Agent
from eden.agents.cli import cli_agent

Effort = Literal["low", "medium", "high", "xhigh"]


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
    """
    if effort is None:
        return cli_agent(
            name="codex",
            model=model,
            binary="codex",
            env=env,
            extra_args=extra_args,
        )

    def _build(ctx: IterationContext) -> list[str]:
        argv: list[str] = [
            "codex",
            "-c",
            f'model_reasoning_effort="{effort}"',
        ]
        argv.extend(extra_args)
        argv.append(ctx.prompt)
        return argv

    return cli_agent(
        name="codex",
        model=model,
        binary="codex",
        build_argv=_build,
        env=env,
        extra_args=extra_args,
    )


__all__ = ["codex"]
