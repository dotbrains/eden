"""Shared helpers for no_sandbox provider tests."""

from __future__ import annotations

from pathlib import Path

from eden.providers._types import CreateOptions


def opts(tmp_path: Path) -> CreateOptions:
    return CreateOptions(
        branch="main",
        worktree_path=tmp_path,
        host_repo_path=tmp_path,
        env={},
        mounts=(),
        name_hint=None,
    )
