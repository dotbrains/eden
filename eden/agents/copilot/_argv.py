"""argv builder for ``copilot -p <prompt> --output-format json ...`` (GH Copilot CLI)."""

from __future__ import annotations

from typing import Literal

Effort = Literal["low", "medium", "high"]


def build_argv(
    *,
    model: str,
    effort: Effort | None,
    extra_args: tuple[str, ...],
    prompt: str,
    allow_all_tools: bool = False,
) -> list[str]:
    """Return the argv vector for a single GitHub Copilot CLI invocation.

    Shape (matches upstream)::

        copilot -p <prompt> --output-format json --model <model>
                [--allow-all-tools] [--effort <level>] [extra_args ...]

    The prompt is passed via ``-p`` (still argv); callers should pre-validate
    its size via :func:`eden.agents._argv_guards.assert_prompt_fits_argv`.
    ``allow_all_tools`` is Copilot's equivalent of Claude's
    ``--dangerously-skip-permissions``.
    """
    argv: list[str] = [
        "copilot",
        "-p",
        prompt,
        "--output-format",
        "json",
        "--model",
        model,
    ]
    if allow_all_tools:
        argv.append("--allow-all-tools")
    if effort is not None:
        argv.extend(["--effort", effort])
    argv.extend(extra_args)
    return argv
