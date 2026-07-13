"""Shared fixtures for sandbox stdin forwarding tests."""

from __future__ import annotations

from pathlib import Path

from eden.providers._types import CreateOptions


def opts(path: Path) -> CreateOptions:
    return CreateOptions(
        branch="main",
        worktree_path=path,
        host_repo_path=path,
        env={},
        mounts=(),
        name_hint=None,
    )


def cat_stdin_script(tmp_path: Path) -> Path:
    """Write a Python script that echoes stdin without shell quoting issues."""
    script = tmp_path / "cat_stdin.py"
    script.write_text("import sys\nsys.stdout.write(sys.stdin.read())\n", encoding="utf-8")
    return script
