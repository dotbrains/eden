"""Shared fixtures for `eden init` CLI tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def repo_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a tmp dir, chdir into it, return the path."""
    repo = tmp_path / "my-repo"
    repo.mkdir()
    monkeypatch.chdir(repo)
    return repo
