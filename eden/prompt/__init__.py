"""Prompt rendering pipeline: built-ins → !`cmd` expansion → arg substitution."""

from __future__ import annotations

from collections.abc import Mapping

from eden.prompt._collect import collect_missing_args, find_missing_keys
from eden.prompt._render import render, render_known
from eden.prompt._shell import expand_shell_blocks
from eden.prompt._source import PromptSource, resolve_source
from eden.providers._protocols import SandboxHandle


def render_prompt(
    *,
    text: str,
    args: Mapping[str, object],
    source_branch: str,
    target_branch: str,
    handle: SandboxHandle,
) -> str:
    """Render ``text`` in three stages.

    1. Substitute built-in ``{{SOURCE_BRANCH}}`` / ``{{TARGET_BRANCH}}``
       placeholders only. User-supplied arg placeholders pass through.
    2. Expand ``!`cmd``` shell blocks via ``handle``.
    3. Substitute the remaining ``{{KEY}}`` placeholders from ``args``.

    Splitting (1) from (3) keeps user-supplied arg values inert: only
    shell blocks written in the raw template are executed, so an arg
    value containing ``!`...``` text is treated as literal data rather
    than triggering subprocess execution.
    """
    built_ins = {"SOURCE_BRANCH": source_branch, "TARGET_BRANCH": target_branch}
    with_built_ins = render_known(text, table=built_ins)
    expanded = expand_shell_blocks(with_built_ins, handle=handle)
    return render(
        expanded,
        args=args,
        source_branch=source_branch,
        target_branch=target_branch,
    )


__all__ = [
    "PromptSource",
    "collect_missing_args",
    "find_missing_keys",
    "render_prompt",
    "resolve_source",
]
