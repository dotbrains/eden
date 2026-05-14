"""Validation + strategy resolution for orchestrator.run()."""

from __future__ import annotations

import subprocess
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

from eden.env import merge_env
from eden.errors import CwdError, InvalidOptions
from eden.prompt._source import resolve_source
from eden.providers._types import BranchStrategy

_KIND_DEFAULT_STRATEGY: dict[str, BranchStrategy] = {
    "none": BranchStrategy.head(),
    "bind_mount": BranchStrategy.merge_to_head(),
    "isolated": BranchStrategy.merge_to_head(),
}


@dataclass(frozen=True)
class SetupResult:
    prompt_text: str
    prompt_is_literal: bool
    cwd: Path
    merged_env: dict[str, str]


def resolve_setup(
    *,
    prompt: str | None,
    prompt_file: str | Path | None,
    prompt_args: Mapping[str, str] | None,
    cwd: Path | None,
    env: Mapping[str, str] | None,
    provider_env: Mapping[str, str],
    sandbox_kind: Literal["none", "bind_mount", "isolated"],
) -> SetupResult:
    source = resolve_source(prompt=prompt, prompt_file=prompt_file, prompt_args=prompt_args)
    merged = merge_env(provider_env, env or {})
    resolved_cwd = _resolve_cwd(cwd)
    return SetupResult(
        prompt_text=source.text,
        prompt_is_literal=source.is_literal,
        cwd=resolved_cwd,
        merged_env=merged,
    )


def _resolve_cwd(cwd: Path | None) -> Path:
    target = cwd if cwd is not None else Path.cwd()
    if not target.exists():
        raise CwdError(message=f"cwd does not exist: {target}")
    if not target.is_dir():
        raise CwdError(message=f"cwd is not a directory: {target}")
    git_dir = target / ".git"
    if not git_dir.exists():
        raise CwdError(
            message=f"cwd is not a git repository: {target}",
            hint="run `git init` or pass a different cwd",
        )
    return target


def resolve_branch_strategy(
    *,
    branch_strategy: BranchStrategy | None,
    sandbox_kind: Literal["none", "bind_mount", "isolated"],
    base_branch: str | None = None,
) -> BranchStrategy:
    if branch_strategy is not None and base_branch is not None:
        raise InvalidOptions(
            code="config.invalid_options",
            message=(
                "base_branch is mutually exclusive with branch_strategy; the "
                "strategy's own `base` controls the fork point"
            ),
            hint="pass base via BranchStrategy.merge_to_head(base=...) or .named(branch, base=...)",
        )
    if branch_strategy is not None:
        return branch_strategy
    default = _KIND_DEFAULT_STRATEGY[sandbox_kind]
    if base_branch is None or default.tag == "head":
        return default
    return replace(default, base=base_branch)


def resolve_target_branch(*, host_repo_path: Path) -> str:
    proc = subprocess.run(
        ["git", "symbolic-ref", "--short", "HEAD"],
        cwd=str(host_repo_path),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return "HEAD"
    return proc.stdout.strip() or "HEAD"
