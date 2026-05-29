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
    extra_args: tuple[str, ...],
    resume_session: str | None = None,
    fork_session: bool = False,
    dangerously_skip_permissions: bool = False,
) -> list[str]:
    """Return the argv vector for a single Claude Code invocation.

    The prompt is delivered via stdin (Eden pipes it via ``-p -``) so the
    Linux 128 KB execve argv limit cannot truncate large prompts.
    ``resume_session``, when set, appends ``--resume <id>`` to continue a
    prior conversation captured by ``capture_sessions``.
    ``fork_session``, when ``True``, also appends ``--fork-session`` so
    Claude writes the continuation under a NEW session id, leaving the
    parent JSONL intact for concurrent fan-out. Requires
    ``resume_session``. Mirrors sandcastle's RunResult.fork() (v0.6.6).
    ``dangerously_skip_permissions``, when ``True``, appends
    ``--dangerously-skip-permissions`` so Claude does not block on
    per-tool permission prompts inside a sandboxed container.
    """
    argv: list[str] = [*_BASE, "--model", model]
    if effort is not None:
        argv.extend(["--thinking-effort", effort])
    if resume_session is not None:
        argv.extend(["--resume", resume_session])
        if fork_session:
            argv.append("--fork-session")
    if dangerously_skip_permissions:
        argv.append("--dangerously-skip-permissions")
    argv.extend(extra_args)
    argv.extend(["-p", "-"])
    return argv
