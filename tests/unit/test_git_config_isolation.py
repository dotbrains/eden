"""Verify tests do not inherit the developer's global git config."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


def test_git_global_config_is_test_scoped() -> None:
    config_path = os.environ.get("GIT_CONFIG_GLOBAL")

    assert config_path is not None
    assert Path(config_path).is_file()


def test_host_global_git_identity_is_hidden() -> None:
    result = subprocess.run(
        ["git", "config", "--global", "--get", "user.email"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert result.stdout == ""
