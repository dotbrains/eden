"""Preflight checks and option normalization for ``eden.run``."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Literal

from eden.agents._protocol import Agent
from eden.errors import InvalidOptions
from eden.output import OutputDefinition
from eden.providers._protocols import SandboxProvider
from eden.providers._types import BranchStrategy


def seconds(value: float | timedelta) -> float:
    if isinstance(value, timedelta):
        return value.total_seconds()
    return float(value)


def maybe_seconds(value: float | timedelta | None) -> float | None:
    if value is None:
        return None
    return seconds(value)


def precheck_resume_session(
    *,
    agent: Agent,
    sandbox: SandboxProvider,
    resume_session: str,
    host_repo_path: Path,
) -> None:
    """Verify the JSONL for ``resume_session`` exists on the host before spawn."""
    from eden.errors import SessionNotFound

    storage = getattr(agent, "session_storage", None)
    locate = getattr(storage, "locate_session_on_host", None)
    if not callable(locate):
        return
    sandbox_cwd = host_repo_path if sandbox.kind == "none" else Path("/workspace")
    found = locate(session_id=resume_session, sandbox_cwd=sandbox_cwd)
    if found is None:
        raise SessionNotFound(session_id=resume_session, agent_name=agent.name)


def validate_session_options(
    *,
    agent: Agent,
    sandbox: SandboxProvider,
    resume_session: str | None,
    fork_session: bool,
    max_iterations: int,
    host_repo_path: Path,
) -> None:
    if resume_session is not None and max_iterations != 1:
        raise InvalidOptions(
            code="config.invalid_options",
            message=(
                "resume_session= is only valid with max_iterations=1; got "
                f"max_iterations={max_iterations}"
            ),
            hint=(
                "resuming a prior session implies a single follow-up turn; "
                "use max_iterations=1 or omit resume_session"
            ),
        )
    if resume_session is not None:
        precheck_resume_session(
            agent=agent,
            sandbox=sandbox,
            resume_session=resume_session,
            host_repo_path=host_repo_path,
        )
    if fork_session and resume_session is None:
        raise InvalidOptions(
            code="config.invalid_options",
            message="fork_session=True requires resume_session=<id>",
            hint=(
                "fork continues a captured session under a new id; "
                "pass resume_session=<id> alongside fork_session=True"
            ),
        )


def validate_output_options(
    *,
    output: OutputDefinition | None,
    max_iterations: int,
    prompt_text: str,
) -> None:
    if output is None:
        return
    if max_iterations != 1:
        raise InvalidOptions(
            code="config.invalid_options",
            message=(
                f"output= is only valid with max_iterations=1; got max_iterations={max_iterations}"
            ),
            hint=(
                "structured output is extracted from the final stdout; "
                "looping iterations would discard intermediate matches"
            ),
        )
    if output.max_retries < 0:
        raise InvalidOptions(
            code="config.invalid_options",
            message=f"output max_retries must be >= 0; got {output.max_retries}",
            hint="use 0 to disable retries (the default), or a positive count",
        )
    tag_marker = f"<{output.tag}>"
    if tag_marker not in prompt_text:
        raise InvalidOptions(
            code="config.invalid_options",
            message=(
                f"output tag {tag_marker} not referenced in prompt; the "
                "agent must be told which tag to emit"
            ),
            hint=(f"include {tag_marker}...{f'</{output.tag}>'} in the prompt instructions"),
        )


def validate_copy_to_worktree(
    *,
    copy_to_worktree: list[str] | None,
    branch_strategy: BranchStrategy | None,
    sandbox_kind: Literal["none", "bind_mount", "isolated"],
    base_branch: str | None,
) -> None:
    if not copy_to_worktree:
        return
    from eden.orchestrator._setup import resolve_branch_strategy

    effective_strategy = resolve_branch_strategy(
        branch_strategy=branch_strategy,
        sandbox_kind=sandbox_kind,
        base_branch=base_branch,
    )
    if effective_strategy.tag == "head":
        raise InvalidOptions(
            code="config.invalid_options",
            message=(
                "copy_to_worktree= is incompatible with branch_strategy 'head'; "
                "the worktree IS the host repo, so copying would overwrite it"
            ),
            hint=(
                "drop copy_to_worktree or pick a branch strategy that carves "
                "a separate worktree (merge_to_head or named)"
            ),
        )


__all__ = [
    "maybe_seconds",
    "precheck_resume_session",
    "seconds",
    "validate_copy_to_worktree",
    "validate_output_options",
    "validate_session_options",
]
