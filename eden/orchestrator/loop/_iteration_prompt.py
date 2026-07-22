"""Prompt rendering for loop iterations."""

from __future__ import annotations

from collections.abc import Mapping

from eden.orchestrator._setup import SetupResult
from eden.prompt import render_prompt
from eden.providers._protocols import SandboxHandle


def render_iteration_prompt(
    *,
    setup: SetupResult,
    prompt_args: Mapping[str, object] | None,
    source_branch: str,
    target_branch: str,
    handle: SandboxHandle,
) -> str:
    if setup.prompt_is_literal:
        # Inline prompts (``prompt="..."``) are passed to the agent verbatim —
        # no ``{{KEY}}`` substitution, no ``!`cmd``` shell expansion, no built-in branch injection.
        return setup.prompt_text
    return render_prompt(
        text=setup.prompt_text,
        args=prompt_args or {},
        source_branch=source_branch,
        target_branch=target_branch,
        handle=handle,
    )


__all__ = ["render_iteration_prompt"]
