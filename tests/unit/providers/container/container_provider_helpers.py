"""Shared helpers for container provider tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from eden.providers._types import CreateOptions

pytestmark = pytest.mark.unit

skip_on_windows = pytest.mark.skipif(
    sys.platform == "win32",
    reason="asserts POSIX `-v` argv shape; Windows host paths use `--mount` "
    "(covered by test_windows_host_paths_use_mount_flag)",
)


def opts(tmp_path: Path) -> CreateOptions:
    return CreateOptions(
        branch="HEAD",
        worktree_path=tmp_path,
        host_repo_path=tmp_path,
        env={},
        mounts=(),
        name_hint="test",
    )


def find_run(captured: list[list[str]]) -> list[str]:
    """Return the first ``<binary> run ...`` command from a captured list."""
    for cmd in captured:
        if len(cmd) >= 2 and cmd[1] == "run":
            return cmd
    raise AssertionError(f"no run cmd in captured: {captured!r}")
