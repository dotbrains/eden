"""Smoke test: docker provider create → exec → close cycle."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from eden.providers._types import CreateOptions
from eden.sandboxes.docker import provider

pytestmark = pytest.mark.integration


def test_create_exec_close(eden_test_image: str, tmp_path: Path) -> None:
    p = provider(image=eden_test_image)
    handle = p.create(
        CreateOptions(
            branch="main",
            worktree_path=tmp_path,
            host_repo_path=tmp_path,
            env={},
            mounts=(),
            name_hint="lifecycle",
        )
    )
    try:
        result = handle.exec("echo hello")
        assert result.exit_code == 0
        assert "hello" in result.stdout
    finally:
        handle.close()


def test_close_removes_container(eden_test_image: str, tmp_path: Path) -> None:
    p = provider(image=eden_test_image)
    handle = p.create(
        CreateOptions(
            branch="main",
            worktree_path=tmp_path,
            host_repo_path=tmp_path,
            env={},
            mounts=(),
            name_hint="cleanup",
        )
    )
    cid = handle.container_id  # type: ignore[attr-defined]
    handle.close()

    inspect = subprocess.run(
        ["docker", "inspect", cid],
        capture_output=True,
        text=True,
    )
    assert inspect.returncode != 0  # gone after kill + --rm
