"""argv builder for `claude --print --output-format stream-json --verbose ...`."""

from __future__ import annotations

from typing import Literal

_BASE: tuple[str, ...] = (
    "claude",
    "--print",
    "--output-format",
    "stream-json",
    "--verbose",
)


def build_argv(
    *,
    model: str,
    effort: Literal["low", "medium", "high"] | None,
    prompt: str,
    extra_args: tuple[str, ...],
) -> list[str]:
    """Return the argv vector for a single Claude Code invocation.

    The prompt is appended as a positional argument after `--` so the shell
    does no parsing of its content.
    """
    argv: list[str] = [*_BASE, "--model", model]
    if effort is not None:
        argv.extend(["--thinking-effort", effort])
    argv.extend(extra_args)
    argv.extend(["--", prompt])
    return argv
