"""Prompt rendering pipeline: source → {{KEY}} substitution → !`cmd` expansion."""

from __future__ import annotations

from collections.abc import Mapping

from eden.prompt._render import render
from eden.prompt._shell import expand_shell_blocks
from eden.prompt._source import resolve_source
from eden.providers._protocols import SandboxHandle


def render_prompt(
    *,
    text: str,
    args: Mapping[str, str],
    source_branch: str,
    target_branch: str,
    handle: SandboxHandle,
) -> str:
    """Render `text` by substituting {{KEY}} then expanding !`cmd` blocks via `handle`."""
    substituted = render(
        text,
        args=args,
        source_branch=source_branch,
        target_branch=target_branch,
    )
    return expand_shell_blocks(substituted, handle=handle)


__all__ = ["render_prompt", "resolve_source"]
