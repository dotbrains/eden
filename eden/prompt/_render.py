"""{{KEY}} substitution with auto-injected built-ins."""

from __future__ import annotations

import re
from collections.abc import Mapping

from eden.errors import PromptError

_KEY_RE = re.compile(r"\{\{(?P<key>[A-Za-z_][A-Za-z0-9_]*)\}\}")


def render(
    text: str,
    *,
    args: Mapping[str, str],
    source_branch: str,
    target_branch: str,
) -> str:
    """Substitute {{KEY}} placeholders. Built-ins win over args."""
    built_ins = {"SOURCE_BRANCH": source_branch, "TARGET_BRANCH": target_branch}
    table: dict[str, str] = {**dict(args), **built_ins}

    def _sub(match: re.Match[str]) -> str:
        key = match.group("key")
        if key not in table:
            known = ", ".join(sorted(table)) or "(none)"
            raise PromptError(
                code="prompt.unknown_key",
                message=f"unknown placeholder {{{{{key}}}}} in prompt",
                hint=f"known keys: {known}",
            )
        return table[key]

    return _KEY_RE.sub(_sub, text)


def render_known(text: str, *, table: Mapping[str, str]) -> str:
    """Substitute only {{KEY}} placeholders present in ``table``.

    Unknown keys pass through verbatim instead of raising — used as a
    pre-pass so built-ins can be substituted inside shell-block bodies
    while user-supplied arg placeholders remain untouched until after
    shell expansion runs.
    """

    def _sub(match: re.Match[str]) -> str:
        key = match.group("key")
        if key in table:
            return table[key]
        return match.group(0)

    return _KEY_RE.sub(_sub, text)
