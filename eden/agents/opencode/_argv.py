"""argv builder for ``opencode run --format json ...``."""

from __future__ import annotations


def build_argv(
    *,
    model: str,
    variant: str | None,
    agent: str | None,
    extra_args: tuple[str, ...],
    prompt: str,
    dangerously_skip_permissions: bool = False,
) -> list[str]:
    """Return the argv vector for a single opencode invocation.

    Shape (matches the upstream contract):

        opencode run --format json --model <model>
                 [--variant <v>] [--agent <name>]
                 [--dangerously-skip-permissions]
                 [extra_args ...]
                 <prompt>

    ``--format json`` is always present so the parser at
    :mod:`eden.agents.opencode._stream` receives structured events instead
    of free-form text. ``dangerously_skip_permissions`` mirrors
    ``claude_code(dangerously_skip_permissions=...)`` ergonomics — safe
    inside isolated sandboxes, dubious for ``no_sandbox()``.
    """
    argv: list[str] = ["opencode", "run", "--format", "json", "--model", model]
    if variant is not None:
        argv.extend(["--variant", variant])
    if agent is not None:
        argv.extend(["--agent", agent])
    if dangerously_skip_permissions:
        argv.append("--dangerously-skip-permissions")
    argv.extend(extra_args)
    argv.append(prompt)
    return argv
