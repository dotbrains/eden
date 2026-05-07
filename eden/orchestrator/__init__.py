"""Public orchestrator surface: run() + create_worktree()."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import timedelta
from pathlib import Path

from eden._types import RunResult, Timeouts
from eden.abort import AbortSignal
from eden.abort._signal import AbortController
from eden.agents._protocol import Agent
from eden.errors import InvalidOptions
from eden.lifecycle import Hooks
from eden.logging._config import Logging
from eden.orchestrator._loop import _run_loop
from eden.orchestrator._setup import resolve_setup
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


def _maybe_seconds(value: float | timedelta | None) -> float | None:
    if value is None:
        return None
    return _seconds(value)


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
    max_iterations: int = 1,
    completion_signal: str | list[str] = "<promise>COMPLETE</promise>",
    idle_timeout: float | timedelta = 600.0,
    idle_warning_interval: float | timedelta | None = None,
    name: str | None = None,
    hooks: Hooks | None = None,
    timeouts: Timeouts | None = None,
    on_event: Callable[[StreamEvent], None] | None = None,
    logging: Logging | None = None,
    signal: AbortSignal | None = None,
    output: OutputDefinition | None = None,
    resume_session: str | None = None,
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
    abort = signal if signal is not None else AbortController().signal
    return _run_loop(
        agent=agent,
        sandbox=sandbox,
        setup=setup,
        branch_strategy=branch_strategy,
        max_iterations=max_iterations,
        completion_signal=completion_signal,
        idle_timeout=_seconds(idle_timeout),
        idle_warning_interval=_maybe_seconds(idle_warning_interval),
        name=name,
        hooks=hooks if hooks is not None else Hooks(),
        timeouts=timeouts if timeouts is not None else Timeouts(),
        on_event=on_event,
        logging_cfg=logging,
        signal=abort,
        prompt_args=prompt_args,
        output=output,
        resume_session=resume_session,
    )


def create_worktree(
    *,
    branch: str | None = None,
    branch_strategy: BranchStrategy | None = None,
    name: str | None = None,
) -> WorktreeHandle:
    """Carve a worktree using Phase 2's create_worktree, with sugar for branch/strategy.

    Returns a WorktreeHandle (context manager) with `.branch`, `.worktree_path`, `.close()`.
    """
    if branch is not None and branch_strategy is not None:
        raise ValueError("branch and branch_strategy are mutually exclusive")
    if branch is not None:
        strategy = BranchStrategy.named(branch)
    elif branch_strategy is not None:
        strategy = branch_strategy
    else:
        strategy = BranchStrategy.merge_to_head()
    return _carve_worktree(
        host_repo_path=Path.cwd(),
        strategy=strategy,
        name_hint=name,
    )


__all__ = ["create_worktree", "run"]
