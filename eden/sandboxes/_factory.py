"""create_sandbox top-level factory + Sandbox context-manager wrapper."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from eden.providers._protocols import SandboxHandle, SandboxProvider
from eden.providers._types import BranchStrategy, CreateOptions, Mount
from eden.sandboxes.errors import UnsupportedStrategy
from eden.worktree._create import WorktreeHandle, create_worktree


@dataclass
class Sandbox:
    worktree: WorktreeHandle
    handle: SandboxHandle
    cwd: Path | None = None

    def __enter__(self) -> Sandbox:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        try:
            self.handle.close()
        finally:
            self.worktree.close()


def create_sandbox(
    *,
    sandbox: SandboxProvider,
    branch: str | None = None,
    branch_strategy: BranchStrategy | None = None,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    mounts: tuple[Mount, ...] | None = None,
    name: str | None = None,
) -> Sandbox:
    """Resolve branch/strategy, carve a worktree, and create the sandbox handle."""
    if branch is not None and branch_strategy is not None:
        raise ValueError("branch and branch_strategy are mutually exclusive")

    if branch is not None:
        strategy = BranchStrategy.named(branch)
    elif branch_strategy is not None:
        strategy = branch_strategy
    elif sandbox.kind == "none":
        strategy = BranchStrategy.head()
    else:
        strategy = BranchStrategy.merge_to_head()

    if not sandbox.supports_strategy(strategy):
        raise UnsupportedStrategy(provider=sandbox.name, strategy=strategy.tag)

    wt = create_worktree(
        host_repo_path=Path.cwd(),
        strategy=strategy,
        name_hint=name,
    )

    try:
        handle = sandbox.create(
            CreateOptions(
                branch=wt.branch,
                worktree_path=wt.worktree_path,
                host_repo_path=wt.host_repo_path,
                env=env or {},
                mounts=mounts or (),
                name_hint=name,
            )
        )
    except Exception:
        wt.close()
        raise

    return Sandbox(worktree=wt, handle=handle, cwd=cwd)
