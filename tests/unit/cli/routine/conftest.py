"""Shared fixtures for `eden routine` CLI tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def repo_dir(tmp_path: Path) -> Path:
    repo = tmp_path / "my-repo"
    repo.mkdir()
    return repo
