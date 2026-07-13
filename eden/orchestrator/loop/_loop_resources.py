"""Resource helpers for the orchestrator loop."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from eden._types import Commit, Iteration
from eden.abort import register_shutdown
from eden.errors import InvalidOptions
from eden.orchestrator._logging import LoopLogger
from eden.orchestrator._setup import SetupResult, resolve_branch_strategy, resolve_target_branch
from eden.providers._protocols import SandboxHandle, SandboxProvider
from eden.providers._types import BranchStrategy
from eden.sandboxes.errors import UnsupportedStrategy
from eden.streaming._bounded_tail import BoundedTail
from eden.worktree._create import WorktreeHandle, create_worktree
from eden.worktree._git import head_sha


@dataclass
class LoopRunResources:
    target_branch: str
    commit_base_sha: str
    collected_commits: list[Commit]
    logger: LoopLogger | None
    handle: SandboxHandle | None
    iterations: list[Iteration]
    stdout_chunks: BoundedTail
    completion_hit: str | None
    rendered_prompt: str


def prepare_loop_worktree(
    *,
    sandbox: SandboxProvider,
    setup: SetupResult,
    branch_strategy: BranchStrategy | None,
    base_branch: str | None,
    name: str | None,
    throw_on_duplicate_worktree: bool,
    git_timeout: float,
    existing_worktree: WorktreeHandle | None,
    existing_handle: SandboxHandle | None,
) -> tuple[WorktreeHandle, bool]:
    caller_managed = existing_worktree is not None and existing_handle is not None
    if caller_managed:
        assert existing_worktree is not None
        if branch_strategy is not None:
            raise InvalidOptions(
                code="config.invalid_options",
                message=(
                    "branch_strategy is incompatible with caller-managed runs; "
                    "the sandbox already owns its worktree and branch"
                ),
            )
        return existing_worktree, caller_managed

    strategy = resolve_branch_strategy(
        branch_strategy=branch_strategy,
        sandbox_kind=sandbox.kind,
        base_branch=base_branch,
    )
    if not sandbox.supports_strategy(strategy):
        raise UnsupportedStrategy(provider=sandbox.name, strategy=strategy.tag)
    worktree = create_worktree(
        host_repo_path=setup.cwd,
        strategy=strategy,
        name_hint=name,
        throw_on_duplicate_worktree=throw_on_duplicate_worktree,
        git_timeout=git_timeout,
    )
    return worktree, caller_managed


def prepare_loop_run_resources(
    *,
    setup: SetupResult,
    worktree: WorktreeHandle,
    caller_managed: bool,
    existing_handle: SandboxHandle | None,
    git_timeout: float,
) -> LoopRunResources:
    target_branch = resolve_target_branch(host_repo_path=setup.cwd)
    commit_base_sha = head_sha(repo_path=worktree.worktree_path, timeout=git_timeout)
    return LoopRunResources(
        target_branch=target_branch,
        commit_base_sha=commit_base_sha,
        collected_commits=[],
        logger=None,
        handle=existing_handle if caller_managed else None,
        iterations=[],
        stdout_chunks=BoundedTail(),
        completion_hit=None,
        rendered_prompt="",
    )


def register_loop_emergency_cleanup(
    *,
    handle: SandboxHandle,
    worktree: WorktreeHandle,
) -> Callable[[], None]:
    def _emergency_cleanup() -> None:
        try:
            handle.close()
        except Exception:
            pass
        try:
            worktree.close()
        except Exception:
            pass

    return register_shutdown(_emergency_cleanup)


__all__ = [
    "LoopRunResources",
    "prepare_loop_run_resources",
    "prepare_loop_worktree",
    "register_loop_emergency_cleanup",
]
