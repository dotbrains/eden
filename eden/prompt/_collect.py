"""Interactive collection of unresolved ``{{KEY}}`` placeholders.

When :func:`eden.interactive` is called with a prompt that references
``{{KEY}}`` placeholders the caller forgot to map in ``prompt_args``,
:func:`collect_missing_args` prompts the user via stdin for each missing
key — instead of failing with :class:`eden.errors.PromptError`. Built-in
keys (``SOURCE_BRANCH`` / ``TARGET_BRANCH``) are skipped because the
orchestrator fills them automatically.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from eden.prompt._render import _KEY_RE

_BUILT_INS = frozenset({"SOURCE_BRANCH", "TARGET_BRANCH"})


def find_missing_keys(text: str, args: Mapping[str, str]) -> tuple[str, ...]:
    """Return placeholder keys referenced in ``text`` but absent from ``args``.

    Order matches first appearance in ``text`` and is deduplicated.
    Built-in keys (``SOURCE_BRANCH`` / ``TARGET_BRANCH``) are filtered
    out — the orchestrator injects them, so they're never "missing" from
    the user's perspective.
    """
    seen: set[str] = set()
    out: list[str] = []
    for match in _KEY_RE.finditer(text):
        key = match.group("key")
        if key in _BUILT_INS or key in args or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return tuple(out)


def _default_prompt(key: str) -> str:
    """Built-in stdin prompt — re-asks until non-empty."""
    while True:
        value = input(f"Enter value for {{{{{key}}}}}: ").strip()
        if value:
            return value
        print(f"  a value is required for {{{{{key}}}}}")


def collect_missing_args(
    text: str,
    args: Mapping[str, str],
    *,
    prompt_fn: Callable[[str], str] | None = None,
) -> dict[str, str]:
    """Return ``args`` merged with values collected for missing keys.

    ``prompt_fn`` is called once per missing key with the key name and
    must return a non-empty string. The default uses :func:`input` and
    re-asks on empty input; tests pass a deterministic stub.

    The returned dict is a fresh copy — ``args`` is not mutated. When no
    keys are missing, returns ``dict(args)`` unchanged.
    """
    missing = find_missing_keys(text, args)
    merged = dict(args)
    if not missing:
        return merged
    pf = prompt_fn if prompt_fn is not None else _default_prompt
    for key in missing:
        merged[key] = pf(key)
    return merged


__all__ = ["collect_missing_args", "find_missing_keys"]
