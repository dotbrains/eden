"""Verify prompt input validation in orchestrator setup."""

from __future__ import annotations

from pathlib import Path

import pytest

from eden.errors import InvalidOptions
from eden.orchestrator._setup import SetupResult, resolve_setup

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
