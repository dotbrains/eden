"""Verify orchestrator setup pipeline: validation, strategy resolution, target branch."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from eden.errors import CwdError, EnvMergeError, InvalidOptions
from eden.orchestrator._setup import (
    SetupResult,
    resolve_branch_strategy,
    resolve_setup,
    resolve_target_branch,
)
from eden.providers._types import BranchStrategy
from eden.sandboxes.no_sandbox import provider as no_sandbox_provider

pytestmark = pytest.mark.unit


def test_resolve_setup_inline_prompt_no_args(tmp_git_repo: Path) -> None:
    result = resolve_setup(
        prompt="hello",
        prompt_file=None,
        prompt_args=None,
        cwd=tmp_git_repo,
        env=None,
        provider_env={},
        sandbox_kind="none",
    )
    assert isinstance(result, SetupResult)
    assert result.prompt_text == "hello"
    assert result.cwd == tmp_git_repo
    assert result.merged_env == {}


def test_resolve_setup_xor_violation_raises() -> None:
    with pytest.raises(InvalidOptions):
        resolve_setup(
            prompt=None,
            prompt_file=None,
            prompt_args=None,
            cwd=None,
            env=None,
            provider_env={},
            sandbox_kind="none",
        )


def test_resolve_setup_env_collision_raises(tmp_git_repo: Path) -> None:
    with pytest.raises(EnvMergeError):
        resolve_setup(
            prompt="x",
            prompt_file=None,
            prompt_args=None,
            cwd=tmp_git_repo,
            env={"K": "1"},
            provider_env={"K": "2"},
            sandbox_kind="none",
        )


def test_resolve_setup_loads_dot_eden_env(tmp_git_repo: Path) -> None:
    eden_dir = tmp_git_repo / ".eden"
    eden_dir.mkdir()
    (eden_dir / ".env").write_text("FROM_FILE=value\n")
    result = resolve_setup(
        prompt="x",
        prompt_file=None,
        prompt_args=None,
        cwd=tmp_git_repo,
        env=None,
        provider_env={},
        sandbox_kind="none",
    )
    assert result.merged_env == {"FROM_FILE": "value"}


def test_resolve_setup_explicit_env_overrides_dot_env(tmp_git_repo: Path) -> None:
    eden_dir = tmp_git_repo / ".eden"
    eden_dir.mkdir()
    (eden_dir / ".env").write_text("KEY=from_file\n")
    result = resolve_setup(
        prompt="x",
        prompt_file=None,
        prompt_args=None,
        cwd=tmp_git_repo,
        env={"KEY": "from_caller"},
        provider_env={},
        sandbox_kind="none",
    )
    assert result.merged_env == {"KEY": "from_caller"}


def test_resolve_setup_provider_env_still_collides_with_dot_env(
    tmp_git_repo: Path,
) -> None:
    eden_dir = tmp_git_repo / ".eden"
    eden_dir.mkdir()
    (eden_dir / ".env").write_text("SHARED=file_value\n")
    with pytest.raises(EnvMergeError):
        resolve_setup(
            prompt="x",
            prompt_file=None,
            prompt_args=None,
            cwd=tmp_git_repo,
            env=None,
            provider_env={"SHARED": "provider_value"},
            sandbox_kind="none",
        )


def test_resolve_setup_cwd_must_exist(tmp_path: Path) -> None:
    missing = tmp_path / "nope"
    with pytest.raises(CwdError):
        resolve_setup(
            prompt="x",
            prompt_file=None,
            prompt_args=None,
            cwd=missing,
            env=None,
            provider_env={},
            sandbox_kind="none",
        )


def test_resolve_setup_cwd_must_be_git_repo(tmp_path: Path) -> None:
    with pytest.raises(CwdError):
        resolve_setup(
            prompt="x",
            prompt_file=None,
            prompt_args=None,
            cwd=tmp_path,
            env=None,
            provider_env={},
            sandbox_kind="none",
        )


def test_resolve_branch_strategy_default_for_none_kind() -> None:
    s = resolve_branch_strategy(branch_strategy=None, sandbox_kind="none")
    assert s.tag == "head"


def test_resolve_branch_strategy_default_for_bind_mount() -> None:
    s = resolve_branch_strategy(branch_strategy=None, sandbox_kind="bind_mount")
    assert s.tag == "merge_to_head"


def test_resolve_branch_strategy_explicit_passes_through() -> None:
    s = resolve_branch_strategy(
        branch_strategy=BranchStrategy.named("feat/x"),
        sandbox_kind="bind_mount",
    )
    assert s.tag == "named"
    assert s.branch == "feat/x"


def test_resolve_branch_strategy_base_branch_overrides_default() -> None:
    s = resolve_branch_strategy(
        branch_strategy=None,
        sandbox_kind="bind_mount",
        base_branch="develop",
    )
    assert s.tag == "merge_to_head"
    assert s.base == "develop"


def test_resolve_branch_strategy_base_branch_ignored_for_head_default() -> None:
    s = resolve_branch_strategy(
        branch_strategy=None,
        sandbox_kind="none",
        base_branch="develop",
    )
    assert s.tag == "head"


def test_resolve_branch_strategy_base_branch_conflicts_with_strategy() -> None:
    with pytest.raises(InvalidOptions):
        resolve_branch_strategy(
            branch_strategy=BranchStrategy.named("feat/x"),
            sandbox_kind="bind_mount",
            base_branch="develop",
        )


def test_resolve_branch_strategy_unsupported_raises() -> None:
    p = no_sandbox_provider()
    s = BranchStrategy.head()
    assert p.supports_strategy(s)


def test_resolve_target_branch_returns_active_branch(tmp_git_repo: Path) -> None:
    out = resolve_target_branch(host_repo_path=tmp_git_repo)
    assert out == "main"


def test_resolve_target_branch_detached_head(tmp_git_repo: Path) -> None:
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=tmp_git_repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    subprocess.run(["git", "checkout", sha], cwd=tmp_git_repo, capture_output=True, check=True)
    out = resolve_target_branch(host_repo_path=tmp_git_repo)
    assert out == "HEAD"
