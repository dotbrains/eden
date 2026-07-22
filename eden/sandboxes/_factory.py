from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from eden._types import Timeouts
from eden.env import load_eden_env
from eden.lifecycle import HookPhase, Hooks
from eden.lifecycle._runner import run_host_hooks, run_sandbox_hooks
from eden.orchestrator._copy_files import apply_copy_to_worktree
from eden.providers._protocols import SandboxProvider
from eden.providers._types import BranchStrategy, CreateOptions, Mount
from eden.sandboxes._factory_validation import raise_copy_to_head_worktree_error
from eden.sandboxes._git_setup import ensure_git_safe_directory
from eden.sandboxes._sandbox import Sandbox
from eden.sandboxes.errors import UnsupportedStrategy
from eden.worktree._create import WorktreeHandle, create_worktree


def create_sandbox(
    *,
    sandbox: SandboxProvider,
    branch: str | None = None,
    branch_strategy: BranchStrategy | None = None,
    base_branch: str | None = None,
    worktree: WorktreeHandle | None = None,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    mounts: tuple[Mount, ...] | None = None,
    name: str | None = None,
    hooks: Hooks | None = None,
    copy_to_worktree: list[str] | None = None,
    throw_on_duplicate_worktree: bool = True,
    timeouts: Timeouts | None = None,
) -> Sandbox:
    """Resolve branch/strategy, carve a worktree, and create a sandbox.

    ``base_branch`` overrides the default ``merge_to_head`` fork point.

    ``worktree`` reuses a caller-managed :class:`WorktreeHandle` (from
    :func:`eden.create_worktree`) instead of carving a fresh one. Ownership is
    split: ``Sandbox.close()`` then tears down the container only, and the
    caller's ``worktree.close()`` decides the worktree's fate — so one
    worktree can host several sequential sandboxes (explore interactively,
    then run AFK; or run agents under different images on one branch).
    Mutually exclusive with ``branch``/``branch_strategy``/``base_branch``,
    whose job (picking the branch) was done when the worktree was carved.

    ``copy_to_worktree`` copies host-relative paths into the worktree before sandbox boot.

    ``hooks`` runs ``host.on_worktree_ready``, ``sandbox.on_sandbox_ready``,
    and ``*.on_close`` from :meth:`Sandbox.close`.

    ``timeouts`` caps the carve's git plumbing and worktree teardown via
    ``Timeouts.git_setup``. Per-run deadlines are passed to each ``sb.run(...)``.
    """
    if branch is not None and branch_strategy is not None:
        raise ValueError("branch and branch_strategy are mutually exclusive")
    if branch_strategy is not None and base_branch is not None:
        raise ValueError(
            "base_branch is mutually exclusive with branch_strategy; "
            "set base via BranchStrategy.merge_to_head(base=...) or .named(branch, base=...)"
        )
    if worktree is not None and (
        branch is not None or branch_strategy is not None or base_branch is not None
    ):
        raise ValueError(
            "worktree is mutually exclusive with branch/branch_strategy/base_branch; "
            "the branch was fixed when the worktree was carved"
        )

    resolved_timeouts = timeouts if timeouts is not None else Timeouts()

    if worktree is not None:
        owns_worktree = False
        wt = worktree
        host_repo_path = wt.host_repo_path
        if copy_to_worktree and wt.worktree_path == wt.host_repo_path:
            raise_copy_to_head_worktree_error(branch_strategy="a head-style worktree")
    else:
        owns_worktree = True
        base = base_branch or "main"
        if branch is not None:
            strategy = BranchStrategy.named(branch, base=base)
        elif branch_strategy is not None:
            strategy = branch_strategy
        elif sandbox.kind == "none":
            strategy = BranchStrategy.head()
        else:
            strategy = BranchStrategy.merge_to_head(base=base)

        if not sandbox.supports_strategy(strategy):
            raise UnsupportedStrategy(provider=sandbox.name, strategy=strategy.tag)

        if copy_to_worktree and strategy.tag == "head":
            raise_copy_to_head_worktree_error(branch_strategy="branch_strategy 'head'")

        host_repo_path = Path.cwd()
        wt = create_worktree(
            host_repo_path=host_repo_path,
            strategy=strategy,
            name_hint=name,
            throw_on_duplicate_worktree=throw_on_duplicate_worktree,
            git_timeout=resolved_timeouts.git_setup,
        )

    combined_env = {**load_eden_env(host_repo_path), **(dict(env) if env else {})}

    try:
        apply_copy_to_worktree(
            paths=copy_to_worktree,
            source_root=host_repo_path,
            worktree_path=wt.worktree_path,
            timeout=resolved_timeouts.copy_to_worktree,
        )
        resolved_hooks = hooks if hooks is not None else Hooks()
        run_host_hooks(
            phase=HookPhase.OnWorktreeReady,
            hooks=resolved_hooks.host,
            worktree_path=wt.worktree_path,
            env=combined_env,
            timeouts=resolved_timeouts,
        )
        handle = sandbox.create(
            CreateOptions(
                branch=wt.branch,
                worktree_path=wt.worktree_path,
                host_repo_path=wt.host_repo_path,
                env=combined_env,
                mounts=mounts or (),
                name_hint=name,
            )
        )
        if sandbox.kind != "none":
            ensure_git_safe_directory(handle, timeout=resolved_timeouts.git_setup)
        try:
            run_sandbox_hooks(
                phase=HookPhase.OnSandboxReady,
                hooks=resolved_hooks.sandbox,
                handle=handle,
                env=combined_env,
                timeouts=resolved_timeouts,
            )
        except Exception:
            try:
                handle.close()
            finally:
                raise
    except Exception:
        # A caller-provided worktree outlives this sandbox by design.
        # Report but suppress cleanup failures so they do not replace creation errors.
        if owns_worktree:
            try:
                wt.close()
            except Exception as cleanup_exc:
                print(f"eden: worktree cleanup also failed: {cleanup_exc}")
        raise

    return Sandbox(
        worktree=wt,
        handle=handle,
        sandbox_provider=sandbox,
        cwd=cwd,
        owns_worktree=owns_worktree,
        hooks=resolved_hooks,
        create_env=combined_env,
        timeouts=resolved_timeouts,
    )
