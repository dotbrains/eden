"""Shared pytest fixtures for the eden test suite."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture(scope="session", autouse=True)
def isolated_git_global_config(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """Keep tests independent of the developer's global git config."""
    previous = os.environ.get("GIT_CONFIG_GLOBAL")
    config_path = tmp_path_factory.mktemp("git-global") / "config"
    config_path.write_text("", encoding="utf-8")
    os.environ["GIT_CONFIG_GLOBAL"] = str(config_path)
    try:
        yield config_path
    finally:
        if previous is None:
            os.environ.pop("GIT_CONFIG_GLOBAL", None)
        else:
            os.environ["GIT_CONFIG_GLOBAL"] = previous


@pytest.fixture
def tmp_git_repo(tmp_path: Path) -> Iterator[Path]:
    """Initialize a tmp git repo with one commit on the `main` branch."""
    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    # Disable signing for the test repo so tests run on machines with a
    # global commit.gpgsign=true policy (or with the agent-runner signing
    # hook active). The fixture has no signing key and shouldn't need one.
    subprocess.run(
        ["git", "config", "commit.gpgsign", "false"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "tag.gpgsign", "false"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    seed = tmp_path / "README.md"
    seed.write_text("seed\n")
    subprocess.run(
        ["git", "add", "README.md"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    yield tmp_path
