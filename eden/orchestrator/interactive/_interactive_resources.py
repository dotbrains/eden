"""Resource preparation for interactive sessions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from eden._types import Timeouts
from eden.abort import AbortSignal
from eden.env import load_eden_env, merge_env
from eden.orchestrator._setup import resolve_target_branch
from eden.orchestrator.interactive._interactive_cwd import resolve_interactive_cwd
from eden.orchestrator.interactive._interactive_setup import (
    resolve_interactive_strategy,
    validate_existing_worktree_options,
)
from eden.prompt._source import resolve_source
from eden.providers._protocols import SandboxProvider
from eden.providers._types import BranchStrategy
from eden.worktree._create import WorktreeHandle, create_worktree


@dataclass(frozen=True)
class InteractiveResources:
    sandbox: SandboxProvider
    cwd_path: Path
    prompt_text: str
    prompt_is_literal: bool
    merged_env: dict[str, str]
    target_branch: str
    timeouts: Timeouts
    worktree: WorktreeHandle


def prepare_interactive_resources(
    *,
    sandbox: SandboxProvider | None,
    signal: AbortSignal | None,
    existing_worktree: WorktreeHandle | None,
    cwd: str | Path | None,
    prompt: str | None,
    prompt_file: str | Path | None,
    prompt_args: Mapping[str, str] | None,
    env: Mapping[str, str] | None,
    branch_strategy: BranchStrategy | None,
    base_branch: str | None,
    copy_to_worktree: list[str] | None,
    name: str | None,
    throw_on_duplicate_worktree: bool,
    timeouts: Timeouts | None,
) -> InteractiveResources:
    if signal is not None:
        signal.raise_if_aborted()

    if sandbox is None:
        from eden.sandboxes.no_sandbox import provider as no_sandbox

        sandbox = no_sandbox()

    validate_existing_worktree_options(
        existing_worktree=existing_worktree,
        branch_strategy=branch_strategy,
        base_branch=base_branch,
        copy_to_worktree=copy_to_worktree,
    )

    cwd_path = resolve_interactive_cwd(existing_worktree=existing_worktree, cwd=cwd)
    prompt_text = ""
    prompt_is_literal = False
    if prompt is not None or prompt_file is not None:
        source = resolve_source(prompt=prompt, prompt_file=prompt_file, prompt_args=prompt_args)
        prompt_text = source.text
        prompt_is_literal = source.is_literal

    caller_env = {**load_eden_env(cwd_path), **(dict(env) if env else {})}
    merged_env = merge_env({}, caller_env)
    strategy = resolve_interactive_strategy(
        sandbox=sandbox,
        existing_worktree=existing_worktree,
        branch_strategy=branch_strategy,
        base_branch=base_branch,
        copy_to_worktree=copy_to_worktree,
    )
    timeouts_or_default = timeouts if timeouts is not None else Timeouts()
    worktree = existing_worktree or create_worktree(
        host_repo_path=cwd_path,
        strategy=strategy,
        name_hint=name,
        throw_on_duplicate_worktree=throw_on_duplicate_worktree,
        git_timeout=timeouts_or_default.git_setup,
    )
    return InteractiveResources(
        sandbox=sandbox,
        cwd_path=cwd_path,
        prompt_text=prompt_text,
        prompt_is_literal=prompt_is_literal,
        merged_env=merged_env,
        target_branch=resolve_target_branch(host_repo_path=cwd_path),
        timeouts=timeouts_or_default,
        worktree=worktree,
    )


__all__ = ["InteractiveResources", "prepare_interactive_resources"]
