"""Verify environment merging in orchestrator setup."""

from __future__ import annotations

from pathlib import Path

import pytest

from eden.errors import EnvMergeError
from eden.orchestrator._setup import resolve_setup

pytestmark = pytest.mark.unit


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
