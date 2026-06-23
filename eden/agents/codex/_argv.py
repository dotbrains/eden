"""argv builder for ``codex exec [resume <id>] --json ...``."""

from __future__ import annotations

from typing import Literal

Effort = Literal["low", "medium", "high", "xhigh"]
ApprovalsReviewer = Literal["user", "auto_review"]


def build_argv(
    *,
    model: str,
    effort: Effort | None,
    extra_args: tuple[str, ...],
    resume_session: str | None = None,
    fork_session: bool = False,
    dangerously_bypass_approvals_and_sandbox: bool = True,
    approvals_reviewer: ApprovalsReviewer | None = None,
) -> list[str]:
    """Return the argv vector for a single codex invocation.

    Shape (matches the upstream contract)::

        codex exec [resume <id> | fork <id>] --json
              [--dangerously-bypass-approvals-and-sandbox]
              -m <model> [-c model_reasoning_effort="<level>"] [extra_args ...]

    The prompt is delivered via stdin (the agent exposes ``stdin_content``),
    so it is not appended to the argv vector.

    ``fork_session``, when ``True``, swaps ``codex exec resume <id>`` for
    ``codex exec fork <id>``, so the continuation writes to a NEW session
    file — concurrent fan-out safe. Requires ``resume_session``.

    ``dangerously_bypass_approvals_and_sandbox`` defaults to ``True`` so the
    codex CLI does not block on per-tool approval prompts inside an isolated
    eden sandbox. Pass ``False`` to keep codex's interactive approvals
    (e.g. when running under ``no_sandbox()``).

    ``approvals_reviewer="auto_review"`` swaps the bypass flag for an
    interactive approval policy plus codex's most permissive sandbox
    (``-a on-request -s danger-full-access -c approvals_reviewer="auto_review"``)
    — auto-review only fires on interactive approvals, and the safety boundary
    becomes the reviewer agent rather than codex's filesystem sandbox (eden's
    sandbox provider still owns the outer boundary). ``"user"`` (and ``None``)
    keep the default bypass behaviour.
    """
    argv: list[str] = ["codex", "exec"]
    if resume_session is not None:
        subcommand = "fork" if fork_session else "resume"
        argv.extend([subcommand, resume_session])
    argv.append("--json")
    if approvals_reviewer == "auto_review":
        argv.extend(
            [
                "-a",
                "on-request",
                "-s",
                "danger-full-access",
                "-c",
                'approvals_reviewer="auto_review"',
            ]
        )
    elif dangerously_bypass_approvals_and_sandbox:
        argv.append("--dangerously-bypass-approvals-and-sandbox")
    argv.extend(["-m", model])
    if effort is not None:
        argv.extend(["-c", f'model_reasoning_effort="{effort}"'])
    argv.extend(extra_args)
    return argv
