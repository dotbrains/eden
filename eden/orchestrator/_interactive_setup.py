"""Setup helpers for ``eden.interactive``."""

from __future__ import annotations

from eden.errors import InvalidOptions
from eden.orchestrator._setup import resolve_branch_strategy
from eden.providers._protocols import SandboxProvider
from eden.providers._types import BranchStrategy
from eden.worktree._create import WorktreeHandle


def validate_existing_worktree_options(
    *,
    existing_worktree: WorktreeHandle | None,
    branch_strategy: BranchStrategy | None,
    base_branch: str | None,
    copy_to_worktree: list[str] | None,
) -> None:
    if existing_worktree is None:
        return
    if branch_strategy is not None or base_branch is not None:
        raise InvalidOptions(
            code="config.invalid_options",
            message=(
                "branch_strategy/base_branch are incompatible with an existing worktree; "
                "the branch was fixed when the worktree was carved"
            ),
        )
    if copy_to_worktree:
        raise InvalidOptions(
            code="config.invalid_options",
            message=(
                "copy_to_worktree= is incompatible with an existing worktree; "
                "seed files when creating the worktree or sandbox"
            ),
        )


def resolve_interactive_strategy(
    *,
    sandbox: SandboxProvider,
    existing_worktree: WorktreeHandle | None,
    branch_strategy: BranchStrategy | None,
    base_branch: str | None,
    copy_to_worktree: list[str] | None,
) -> BranchStrategy:
    # Interactive sessions default to ``head`` when the provider supports it:
    # interactive UX expects agent writes to land in the host repo directly.
    if existing_worktree is not None:
        strategy = BranchStrategy.named(existing_worktree.branch)
    elif branch_strategy is not None and base_branch is not None:
        raise InvalidOptions(
            code="config.invalid_options",
            message=(
                "base_branch is mutually exclusive with branch_strategy; the "
                "strategy's own `base` controls the fork point"
            ),
            hint="pass base via BranchStrategy.merge_to_head(base=...) or .named(branch, base=...)",
        )
    elif branch_strategy is not None:
        strategy = branch_strategy
    elif sandbox.supports_strategy(BranchStrategy.head()):
        strategy = BranchStrategy.head()
    else:
        strategy = resolve_branch_strategy(
            branch_strategy=None,
            sandbox_kind=sandbox.kind,
            base_branch=base_branch,
        )

    if not sandbox.supports_strategy(strategy):
        from eden.sandboxes.errors import UnsupportedStrategy

        raise UnsupportedStrategy(provider=sandbox.name, strategy=strategy.tag)

    if copy_to_worktree and strategy.tag == "head":
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
    return strategy


__all__ = ["resolve_interactive_strategy", "validate_existing_worktree_options"]
