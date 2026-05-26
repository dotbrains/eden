"""argv builder for ``agent --print --output-format stream-json ...`` (Cursor CLI)."""

from __future__ import annotations


def build_argv(
    *,
    model: str,
    extra_args: tuple[str, ...],
    prompt: str,
    force: bool = False,
) -> list[str]:
    """Return the argv vector for a single cursor invocation.

    Cursor's CLI binary is named ``agent`` (not ``cursor``); the invocation
    is::

        agent --print --output-format stream-json --model <model>
              [--force] [extra_args ...] <prompt>

    The prompt is passed positionally, so callers should pre-validate its
    size via :func:`eden.agents._argv_guards.assert_prompt_fits_argv`.
    ``force`` skips permission prompts (cursor's equivalent of Claude's
    ``--dangerously-skip-permissions``).
    """
    argv: list[str] = [
        "agent",
        "--print",
        "--output-format",
        "stream-json",
        "--model",
        model,
    ]
    if force:
        argv.append("--force")
    argv.extend(extra_args)
    argv.append(prompt)
    return argv
