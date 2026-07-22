"""Prompt rendering for interactive sessions."""

from __future__ import annotations

import sys
from collections.abc import Mapping

from eden.prompt import render_prompt
from eden.prompt._collect import collect_missing_args
from eden.providers._protocols import SandboxHandle


def render_interactive_prompt(
    *,
    prompt_text: str,
    prompt_is_literal: bool,
    prompt_args: Mapping[str, object] | None,
    collect_args: bool | None,
    source_branch: str,
    target_branch: str,
    handle: SandboxHandle,
) -> str:
    if not prompt_text:
        return ""
    if prompt_is_literal:
        # Inline prompts are passed to the agent verbatim: no substitution, no
        # shell expansion, no built-in injection.
        return prompt_text

    effective_args: Mapping[str, object] = prompt_args or {}
    should_collect = collect_args if collect_args is not None else sys.stdin.isatty()
    if should_collect:
        effective_args = collect_missing_args(prompt_text, effective_args)
    return render_prompt(
        text=prompt_text,
        args=effective_args,
        source_branch=source_branch,
        target_branch=target_branch,
        handle=handle,
    )


__all__ = ["render_interactive_prompt"]
