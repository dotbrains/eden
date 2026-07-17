"""{{KEY}} substitution with auto-injected built-ins."""

from __future__ import annotations

import re
import warnings
from collections.abc import Mapping

from eden.errors import PromptError

_KEY_RE = re.compile(r"\{\{\s*(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*\}\}")


def render(
    text: str,
    *,
    args: Mapping[str, object],
    source_branch: str,
    target_branch: str,
) -> str:
    """Substitute {{KEY}} placeholders. Built-ins win over args."""
    built_ins = {"SOURCE_BRANCH": source_branch, "TARGET_BRANCH": target_branch}
    table: dict[str, str] = {**_normalize_args(args), **built_ins}
    used: set[str] = set()

    def _sub(match: re.Match[str]) -> str:
        key = match.group("key")
        if key not in table:
            known = ", ".join(sorted(table)) or "(none)"
            raise PromptError(
                code="prompt.unknown_key",
                message=f"unknown placeholder {{{{{key}}}}} in prompt",
                hint=f"known keys: {known}",
            )
        used.add(key)
        return table[key]

    rendered = _KEY_RE.sub(_sub, text)
    unused = sorted(set(args) - used)
    if unused:
        warnings.warn(
            f"unused prompt_args keys: {', '.join(unused)}",
            UserWarning,
            stacklevel=2,
        )
    return rendered


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


def _normalize_args(args: Mapping[str, object]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in args.items():
        if value is None:
            raise PromptError(
                code="prompt.missing_arg",
                message=f"prompt_args value for {{{{{key}}}}} is missing",
                hint=f"pass a non-empty string for prompt_args[{key!r}]",
            )
        if not isinstance(value, str):
            raise PromptError(
                code="prompt.invalid_arg",
                message=(
                    f"prompt_args value for {{{{{key}}}}} must be a string, "
                    f"got {type(value).__name__}"
                ),
                hint=f"convert prompt_args[{key!r}] to a string before calling Eden",
            )
        normalized[key] = value
    return normalized
