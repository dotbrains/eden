"""Sandbox-side git setup shared by run/create_sandbox/interactive."""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

from eden.providers._protocols import SandboxHandle


def _normalize_git_path(value: str) -> str:
    return value.replace("\\", "/").rstrip("/")


def configure_sandbox_git(
    handle: SandboxHandle,
    host_repo_path: Path,
    *,
    timeout: float,
) -> None:
    """Configure sandbox git defaults that should mirror the host repo."""
    _ensure_git_safe_directory(handle, timeout=timeout)
    name = _host_git_config(host_repo_path, "user.name")
    email = _host_git_config(host_repo_path, "user.email")
    if name:
        _set_global_git_config(handle, "user.name", name, timeout=timeout)
    if email:
        _set_global_git_config(handle, "user.email", email, timeout=timeout)


def _ensure_git_safe_directory(handle: SandboxHandle, *, timeout: float) -> None:
    worktree_path: Path = handle.worktree_path
    target = _normalize_git_path(worktree_path.as_posix())
    current = handle.exec(
        "git config --global --get-all safe.directory || true",
        timeout=timeout,
    )
    configured = {_normalize_git_path(line.strip()) for line in current.stdout.splitlines()}
    if target in configured:
        return

    result = handle.exec(
        f"git config --global --add safe.directory {shlex.quote(worktree_path.as_posix())}",
        timeout=timeout,
    )
    if result.exit_code != 0:
        raise RuntimeError(f"failed to configure git safe.directory: {result.stderr.strip()}")


def _host_git_config(host_repo_path: Path, key: str) -> str:
    result = subprocess.run(
        ["git", "config", "--local", key],
        cwd=str(host_repo_path),
        capture_output=True,
        text=True,
        timeout=10.0,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _set_global_git_config(
    handle: SandboxHandle,
    key: str,
    value: str,
    *,
    timeout: float,
) -> None:
    result = handle.exec(
        f"git config --global {shlex.quote(key)} {shlex.quote(value)}",
        timeout=timeout,
    )
    if result.exit_code != 0:
        raise RuntimeError(f"failed to configure git {key}: {result.stderr.strip()}")


__all__ = ["configure_sandbox_git"]
