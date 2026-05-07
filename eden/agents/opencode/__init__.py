"""opencode CLI agent."""

from __future__ import annotations

from collections.abc import Mapping

from eden.agents._context import IterationContext
from eden.agents._protocol import Agent
from eden.agents.cli import cli_agent


def opencode(
    model: str = "claude-opus-4",
    *,
    variant: str | None = None,
    env: Mapping[str, str] | None = None,
    extra_args: tuple[str, ...] = (),
) -> Agent:
    """opencode CLI agent (sst/opencode). Assumes ``opencode`` binary is on PATH.

    Args:
        model: Model identifier passed via ``--model``. Default
            ``"claude-opus-4"`` is illustrative — opencode supports multiple
            providers; override per call site.
        variant: Optional reasoning-effort variant passed via ``--variant``
            (e.g. ``"high"``, ``"max"``, ``"low"``, ``"minimal"``).
        env: Per-agent environment additions (merged by the orchestrator).
        extra_args: Inserted between ``--variant`` (if any) and the prompt.
    """

    def _build(ctx: IterationContext) -> list[str]:
        argv: list[str] = ["opencode", "run", "--model", model]
        if variant is not None:
            argv.extend(["--variant", variant])
        argv.extend(extra_args)
        argv.append(ctx.prompt)
        return argv

    return cli_agent(
        name="opencode",
        model=model,
        binary="opencode",
        build_argv=_build,
        env=env,
        extra_args=extra_args,
    )


__all__ = ["opencode"]
