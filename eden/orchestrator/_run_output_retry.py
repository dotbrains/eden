"""Structured-output retry orchestration for ``eden.run``."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path

from eden._types import RunResult
from eden.errors import SessionNotFound, StructuredOutputError
from eden.orchestrator._setup import SetupResult, resolve_setup
from eden.output import OutputDefinition
from eden.providers._protocols import SandboxProvider


def corrective_output_prompt(output: OutputDefinition, exc: Exception) -> str:
    """Build the follow-up prompt sent when structured-output extraction fails."""
    message = getattr(exc, "message", str(exc))
    cause = getattr(exc, "cause", None)
    detail = f" ({cause})" if cause else ""
    tag = output.tag
    return (
        f"Your previous response could not be used: {message}{detail}. "
        f"Re-emit the complete <{tag}>...</{tag}> block with corrected, valid "
        "content and nothing after the closing tag."
    )


def run_with_output_retries(
    *,
    output: OutputDefinition,
    setup: SetupResult,
    resume_session: str | None,
    fork_session: bool,
    max_retries: int,
    invoke: Callable[[SetupResult, str | None, bool], RunResult],
    precheck_resume: Callable[[str], None],
    prompt_args: Mapping[str, str] | None,
    cwd_path: Path | None,
    env: Mapping[str, str] | None,
    sandbox: SandboxProvider,
) -> RunResult:
    cur_setup, cur_resume, cur_fork = setup, resume_session, fork_session
    attempt = 0
    while True:
        try:
            return invoke(cur_setup, cur_resume, cur_fork)
        except StructuredOutputError as exc:
            if attempt >= max_retries:
                raise
            attempt += 1
            use_resume = exc.session_id is not None
            if use_resume:
                try:
                    precheck_resume(exc.session_id)  # type: ignore[arg-type]
                except SessionNotFound:
                    use_resume = False
            if use_resume:
                cur_setup = resolve_setup(
                    prompt=corrective_output_prompt(output, exc),
                    prompt_file=None,
                    prompt_args=prompt_args,
                    cwd=cwd_path,
                    env=env,
                    provider_env={},
                    sandbox_kind=sandbox.kind,
                )
                cur_resume, cur_fork = exc.session_id, False
            else:
                cur_setup, cur_resume, cur_fork = setup, None, False


__all__ = ["corrective_output_prompt", "run_with_output_retries"]
