"""Verify docker exec wiring: cwd, env, on_line, exit codes."""

from __future__ import annotations

from pathlib import Path

import pytest

from eden.providers._types import CreateOptions
from eden.sandboxes.docker import provider

pytestmark = pytest.mark.integration


@pytest.fixture
def handle(eden_test_image: str, tmp_path: Path):  # type: ignore[no-untyped-def]
    p = provider(image=eden_test_image)
    h = p.create(
        CreateOptions(
            branch="main",
            worktree_path=tmp_path,
            host_repo_path=tmp_path,
            env={"GLOBAL": "global-val"},
            mounts=(),
            name_hint="exec",
        )
    )
    yield h
    h.close()


def test_default_cwd_is_workspace(handle) -> None:  # type: ignore[no-untyped-def]
    result = handle.exec("pwd")
    assert "/workspace" in result.stdout


def test_explicit_cwd_overrides(handle) -> None:  # type: ignore[no-untyped-def]
    result = handle.exec("pwd", cwd=Path("/tmp"))
    assert "/tmp" in result.stdout


def test_env_visible_to_command(handle) -> None:  # type: ignore[no-untyped-def]
    result = handle.exec("echo $GLOBAL")
    assert "global-val" in result.stdout


def test_per_call_env_overrides(handle) -> None:  # type: ignore[no-untyped-def]
    result = handle.exec("echo $LOCAL", env={"LOCAL": "x"})
    assert "x" in result.stdout


def test_nonzero_exit_returned(handle) -> None:  # type: ignore[no-untyped-def]
    result = handle.exec("exit 7")
    assert result.exit_code == 7


def test_on_line_callback_invoked(handle) -> None:  # type: ignore[no-untyped-def]
    seen: list[str] = []
    handle.exec("echo a; echo b", on_line=seen.append)
    assert "a" in seen
    assert "b" in seen
