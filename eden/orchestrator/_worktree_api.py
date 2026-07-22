"""Public worktree convenience API."""

from __future__ import annotations

from pathlib import Path

from eden._types import Timeouts
from eden.errors import InvalidOptions
from eden.lifecycle import HookPhase, Hooks
from eden.lifecycle._runner import run_host_hooks
from eden.orchestrator._copy_files import apply_copy_to_worktree
from eden.providers._types import BranchStrategy
from eden.worktree._create import WorktreeHandle
from eden.worktree._create import create_worktree as _carve_worktree


def create_worktree(
    *,
    branch: str | None = None,
    branch_strategy: BranchStrategy | None = None,
    base_branch: str | None = None,
    cwd: str | Path | None = None,
    copy_to_worktree: list[str] | None = None,
    hooks: Hooks | None = None,
    timeouts: Timeouts | None = None,
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
    host_repo_path = Path(cwd) if cwd is not None else Path.cwd()
    timeouts_or_default = timeouts if timeouts is not None else Timeouts()
    wt = _carve_worktree(
        host_repo_path=host_repo_path,
        strategy=strategy,
        name_hint=name,
        throw_on_duplicate_worktree=throw_on_duplicate_worktree,
        git_timeout=timeouts_or_default.git_setup,
    )
    try:
        apply_copy_to_worktree(
            paths=copy_to_worktree,
            source_root=host_repo_path,
            worktree_path=wt.worktree_path,
            timeout=timeouts_or_default.copy_to_worktree,
        )
        run_host_hooks(
            phase=HookPhase.OnWorktreeReady,
            hooks=(hooks if hooks is not None else Hooks()).host,
            worktree_path=wt.worktree_path,
            env={},
            timeouts=timeouts_or_default,
        )
    except BaseException:
        wt.close()
        raise
    return wt
