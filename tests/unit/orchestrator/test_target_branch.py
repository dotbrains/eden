"""Verify target branch detection for orchestrator setup."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from eden.orchestrator._setup import resolve_target_branch

pytestmark = pytest.mark.unit


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
