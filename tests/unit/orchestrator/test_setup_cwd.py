"""Verify cwd validation in orchestrator setup."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from eden.errors import CwdError
from eden.orchestrator._setup import resolve_setup

pytestmark = pytest.mark.unit


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


def test_resolve_setup_cwd_returns_absolute_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    monkeypatch.chdir(tmp_path)

    result = resolve_setup(
        prompt="x",
        prompt_file=None,
        prompt_args=None,
        cwd=Path("repo"),
        env=None,
        provider_env={},
        sandbox_kind="none",
    )

    assert result.cwd == repo.resolve()
