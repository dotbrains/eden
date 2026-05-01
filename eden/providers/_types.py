"""Frozen dataclasses and aliases for the provider surface."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

StrategyTag = Literal["head", "merge_to_head", "named"]


@dataclass(frozen=True)
class BranchStrategy:
    tag: StrategyTag
    branch: str | None = None
    base: str = "main"

    @staticmethod
    def head() -> BranchStrategy:
        return BranchStrategy(tag="head")

    @staticmethod
    def merge_to_head(base: str = "main") -> BranchStrategy:
        return BranchStrategy(tag="merge_to_head", base=base)

    @staticmethod
    def named(branch: str, base: str = "main") -> BranchStrategy:
        return BranchStrategy(tag="named", branch=branch, base=base)


@dataclass(frozen=True)
class Mount:
    host: Path
    sandbox: Path
    read_only: bool = False


@dataclass(frozen=True)
class ExecResult:
    stdout: str
    stderr: str
    exit_code: int

    @property
    def ok(self) -> bool:
        return self.exit_code == 0

    def check(self) -> ExecResult:
        if self.ok:
            return self
        # Lazy import to avoid eden.providers ↔ eden.sandboxes cycle.
        from eden.sandboxes.errors import ExecFailed

        raise ExecFailed(result=self, argv_or_cmd="<see result>")


@dataclass(frozen=True)
class CreateOptions:
    branch: str
    worktree_path: Path
    host_repo_path: Path
    env: Mapping[str, str]
    mounts: tuple[Mount, ...]
    name_hint: str | None
