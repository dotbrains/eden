"""Public orchestrator surface: run() + create_worktree()."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import timedelta
from pathlib import Path

from eden._types import RunResult, Timeouts
from eden.abort import AbortSignal
from eden.abort._signal import AbortController
from eden.agents._protocol import Agent
from eden.errors import InvalidOptions, StructuredOutputError
from eden.lifecycle import Hooks
from eden.logging._config import Logging
from eden.orchestrator._loop import _run_loop
from eden.orchestrator._setup import SetupResult, resolve_setup
from eden.output import OutputDefinition
from eden.providers._protocols import SandboxProvider
from eden.providers._types import BranchStrategy
from eden.streaming import StreamEvent
from eden.worktree._create import WorktreeHandle
from eden.worktree._create import create_worktree as _carve_worktree


def _seconds(value: float | timedelta) -> float:
    if isinstance(value, timedelta):
        return value.total_seconds()
    return float(value)


def _precheck_resume_session(
    *,
    agent: Agent,
    sandbox: SandboxProvider,
    resume_session: str,
    host_repo_path: Path,
) -> None:
    """Verify the JSONL for ``resume_session`` exists on the host before spawn.

    Fast, host-side, structured. Without this the agent would fail inside
    the sandbox with a buried "session not found" stderr.

    Skipped silently when the agent's ``session_storage`` does not
    implement :meth:`LocatableSessionStorage.locate_session_on_host`
    (back-compat for custom storage impls).
    """
    from eden.errors import SessionNotFound

    storage = getattr(agent, "session_storage", None)
    locate = getattr(storage, "locate_session_on_host", None)
    if not callable(locate):
        return
    sandbox_cwd = host_repo_path if sandbox.kind == "none" else Path("/workspace")
    found = locate(session_id=resume_session, sandbox_cwd=sandbox_cwd)
    if found is None:
        raise SessionNotFound(session_id=resume_session, agent_name=agent.name)


def _maybe_seconds(value: float | timedelta | None) -> float | None:
    if value is None:
        return None
    return _seconds(value)


def _corrective_output_prompt(output: OutputDefinition, exc: Exception) -> str:
    """Build the follow-up prompt sent when structured-output extraction fails.

    Quotes the failure so the agent knows what to fix, and re-states the tag so
    it re-emits a valid block. ``getattr`` keeps it robust to error shape.
    """
    message = getattr(exc, "message", str(exc))
    cause = getattr(exc, "cause", None)
    detail = f" ({cause})" if cause else ""
    tag = output.tag
    return (
        f"Your previous response could not be used: {message}{detail}. "
        f"Re-emit the complete <{tag}>...</{tag}> block with corrected, valid "
        "content and nothing after the closing tag."
    )


def run(
    *,
    agent: Agent,
    sandbox: SandboxProvider,
    prompt: str | None = None,
    prompt_file: str | Path | None = None,
    prompt_args: Mapping[str, str] | None = None,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    branch_strategy: BranchStrategy | None = None,
    base_branch: str | None = None,
    max_iterations: int = 1,
    completion_signal: str | list[str] = "<promise>COMPLETE</promise>",
    idle_timeout: float | timedelta = 600.0,
    idle_warning_interval: float | timedelta | None = None,
    completion_timeout: float | timedelta | None = 60.0,
    name: str | None = None,
    hooks: Hooks | None = None,
    timeouts: Timeouts | None = None,
    on_event: Callable[[StreamEvent], None] | None = None,
    logging: Logging | None = None,
    signal: AbortSignal | None = None,
    output: OutputDefinition | None = None,
    resume_session: str | None = None,
    fork_session: bool = False,
    copy_to_worktree: list[str] | None = None,
    throw_on_duplicate_worktree: bool = True,
) -> RunResult:
    """Run an agent against a sandbox in a managed worktree, returning RunResult."""
    cwd_path = Path(cwd) if cwd is not None else None
    provider_env: dict[str, str] = {}
    setup = resolve_setup(
        prompt=prompt,
        prompt_file=prompt_file,
        prompt_args=prompt_args,
        cwd=cwd_path,
        env=env,
        provider_env=provider_env,
        sandbox_kind=sandbox.kind,
    )
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
        _precheck_resume_session(
            agent=agent,
            sandbox=sandbox,
            resume_session=resume_session,
            host_repo_path=setup.cwd,
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
    if output is not None:
        if max_iterations != 1:
            raise InvalidOptions(
                code="config.invalid_options",
                message=(
                    "output= is only valid with max_iterations=1; got "
                    f"max_iterations={max_iterations}"
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
        if tag_marker not in setup.prompt_text:
            raise InvalidOptions(
                code="config.invalid_options",
                message=(
                    f"output tag {tag_marker} not referenced in prompt; the "
                    "agent must be told which tag to emit"
                ),
                hint=(f"include {tag_marker}...{f'</{output.tag}>'} in the prompt instructions"),
            )
    if copy_to_worktree:
        from eden.orchestrator._setup import resolve_branch_strategy

        effective_strategy = resolve_branch_strategy(
            branch_strategy=branch_strategy,
            sandbox_kind=sandbox.kind,
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
    abort = signal if signal is not None else AbortController().signal

    def _invoke(setup_: SetupResult, resume_: str | None, fork_: bool) -> RunResult:
        return _run_loop(
            agent=agent,
            sandbox=sandbox,
            setup=setup_,
            branch_strategy=branch_strategy,
            base_branch=base_branch,
            max_iterations=max_iterations,
            completion_signal=completion_signal,
            idle_timeout=_seconds(idle_timeout),
            idle_warning_interval=_maybe_seconds(idle_warning_interval),
            completion_timeout=_maybe_seconds(completion_timeout),
            name=name,
            hooks=hooks if hooks is not None else Hooks(),
            timeouts=timeouts if timeouts is not None else Timeouts(),
            on_event=on_event,
            logging_cfg=logging,
            signal=abort,
            prompt_args=prompt_args,
            output=output,
            resume_session=resume_,
            fork_session=fork_,
            copy_to_worktree=copy_to_worktree,
            throw_on_duplicate_worktree=throw_on_duplicate_worktree,
        )

    max_retries = output.max_retries if output is not None else 0
    if max_retries <= 0:
        return _invoke(setup, resume_session, fork_session)

    # Structured-output retry loop (upstream's Output maxRetries). On an
    # extraction/validation failure, resume the failing session with corrective
    # feedback so the agent re-emits a valid block without repeating the work;
    # for agents without session capture (no session_id), fall back to a fresh
    # re-run of the original prompt. ``copy_to_worktree`` is dropped on resume
    # retries: those carve a fresh worktree and the seeded files are already in
    # the resumed conversation's context.
    from eden.errors import SessionNotFound

    assert output is not None  # max_retries > 0 implies output was configured
    cur_setup, cur_resume, cur_fork = setup, resume_session, fork_session
    attempt = 0
    while True:
        try:
            return _invoke(cur_setup, cur_resume, cur_fork)
        except StructuredOutputError as exc:
            if attempt >= max_retries:
                raise
            attempt += 1
            use_resume = exc.session_id is not None
            if use_resume:
                try:
                    _precheck_resume_session(
                        agent=agent,
                        sandbox=sandbox,
                        resume_session=exc.session_id,  # type: ignore[arg-type]
                        host_repo_path=setup.cwd,
                    )
                except SessionNotFound:
                    use_resume = False
            if use_resume:
                cur_setup = resolve_setup(
                    prompt=_corrective_output_prompt(output, exc),
                    prompt_file=None,
                    prompt_args=prompt_args,
                    cwd=cwd_path,
                    env=env,
                    provider_env={},
                    sandbox_kind=sandbox.kind,
                )
                cur_resume, cur_fork = exc.session_id, False
            else:
                # Fresh fallback: re-run the original prompt unchanged.
                cur_setup, cur_resume, cur_fork = setup, None, False


def create_worktree(
    *,
    branch: str | None = None,
    branch_strategy: BranchStrategy | None = None,
    base_branch: str | None = None,
    name: str | None = None,
    throw_on_duplicate_worktree: bool = True,
) -> WorktreeHandle:
    """Carve a worktree using Phase 2's create_worktree, with sugar for branch/strategy.

    Returns a WorktreeHandle (context manager) with `.branch`, `.worktree_path`, `.close()`.

    ``base_branch`` overrides the fork point of the default ``merge_to_head``
    strategy; it is mutually exclusive with ``branch_strategy`` (whose own
    ``base`` field already controls the fork point).
    """
    if branch is not None and branch_strategy is not None:
        raise ValueError("branch and branch_strategy are mutually exclusive")
    if branch_strategy is not None and base_branch is not None:
        raise ValueError(
            "base_branch is mutually exclusive with branch_strategy; "
            "set base via BranchStrategy.merge_to_head(base=...) or .named(branch, base=...)"
        )
    if branch is not None:
        strategy = BranchStrategy.named(branch, base=base_branch or "main")
    elif branch_strategy is not None:
        strategy = branch_strategy
    else:
        strategy = BranchStrategy.merge_to_head(base=base_branch or "main")
    return _carve_worktree(
        host_repo_path=Path.cwd(),
        strategy=strategy,
        name_hint=name,
        throw_on_duplicate_worktree=throw_on_duplicate_worktree,
    )


__all__ = ["create_worktree", "run"]
