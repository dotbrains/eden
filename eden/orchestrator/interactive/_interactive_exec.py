"""Interactive agent argv construction and TTY dispatch."""

from __future__ import annotations

import inspect
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from eden.abort import AbortSignal
from eden.agents._context import IterationContext
from eden.agents._flox import flox_wrap
from eden.agents._protocol import Agent
from eden.errors import InvalidOptions
from eden.providers._protocols import SandboxHandle


def build_interactive_argv(
    *,
    agent: Agent,
    rendered_prompt: str,
    handle: SandboxHandle,
    worktree_path: Path,
    branch: str,
    name: str | None,
) -> list[str]:
    ctx = IterationContext(
        iteration=0,
        prompt=rendered_prompt,
        sandbox_handle=handle,
        worktree_path=worktree_path,
        branch=branch,
        name=name,
    )
    build_interactive = getattr(agent, "build_interactive_command", None)
    argv = build_interactive(ctx) if callable(build_interactive) else agent.build_command(ctx)
    # Per-agent Flox runtime (ADR-0014): wrap before the handle wraps argv in
    # ``<binary> exec -it``, so for container providers ``flox`` runs inside
    # the container. For no_sandbox the wrap runs on the host.
    return flox_wrap(argv, flox_env=getattr(agent, "flox_env", None))


def run_interactive_exec(
    *,
    handle: SandboxHandle,
    sandbox_name: str,
    argv: list[str],
    env: Mapping[str, str],
    signal: AbortSignal | None,
) -> int:
    ix = getattr(handle, "interactive_exec", None)
    if not callable(ix):
        raise InvalidOptions(
            code="config.invalid_options",
            message=(f"sandbox={sandbox_name!r} does not expose an interactive TTY"),
            hint=(
                "use eden.run() for non-interactive runs against this provider, "
                "or pick no_sandbox / docker / podman for interactive sessions"
            ),
        )

    # The exec runs inside the sandbox, so cwd is the in-container worktree
    # path (``handle.worktree_path``), not the host path.
    interactive_params: Mapping[str, inspect.Parameter]
    try:
        interactive_params = inspect.signature(ix).parameters
    except (TypeError, ValueError):
        interactive_params = {}
    if "signal" in interactive_params:
        return cast(int, ix(argv, cwd=handle.worktree_path, env=env, signal=signal))
    return cast(int, ix(argv, cwd=handle.worktree_path, env=env))


__all__ = ["build_interactive_argv", "run_interactive_exec"]
