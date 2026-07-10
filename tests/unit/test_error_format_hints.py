"""Tests for synthesized error formatter hints."""

from __future__ import annotations

from pathlib import Path

import pytest

from eden import format_error_message
from eden.providers._types import ExecResult
from eden.sandboxes.errors import (
    ContainerStartFailed,
    ExecFailed,
    ExecTimeout,
    ImageNotFound,
    ImageUidMismatch,
    MountConfigError,
    ProviderUnavailable,
    UnsupportedStrategy,
)
from eden.worktree.errors import BranchExists, DirtyHostBlocked, GitCommandFailed, WorktreeLocked

pytestmark = pytest.mark.unit


def test_provider_unavailable_synthesises_docker_hint() -> None:
    err = ProviderUnavailable(provider="docker", binary="docker")
    out = format_error_message(err)
    assert "Sandbox operation failed:" in out
    assert "Is Docker running?" in out


def test_provider_unavailable_synthesises_podman_hint() -> None:
    err = ProviderUnavailable(provider="podman", binary="podman")
    out = format_error_message(err)
    assert "podman" in out.lower()


def test_provider_unavailable_falls_back_to_generic_hint() -> None:
    err = ProviderUnavailable(provider="something-custom", binary="custom-bin")
    out = format_error_message(err)
    assert "PATH" in out
    assert "custom-bin" in out


def test_image_not_found_synthesises_build_hint() -> None:
    err = ImageNotFound(image="my-img:latest", stderr="No such image")
    out = format_error_message(err)
    assert "docker build" in out
    assert "my-img:latest" in out


def test_container_start_failed_synthesises_hint() -> None:
    err = ContainerStartFailed(image="my:img", exit_code=125, stderr="oops")
    out = format_error_message(err)
    assert "container exited" in out.lower() or "Docker daemon" in out


def test_image_uid_mismatch_synthesises_hint() -> None:
    err = ImageUidMismatch(image="x:y", image_uid=1000, expected_uid=501)
    out = format_error_message(err)
    assert "AGENT_UID" in out


def test_mount_config_error_synthesises_hint() -> None:
    err = MountConfigError(sandbox_path="/foo", parent="/", sandbox_homedir="/home/agent")
    out = format_error_message(err)
    assert "sandbox HOME" in out or "parent directory" in out


def test_exec_timeout_synthesises_hint() -> None:
    err = ExecTimeout(cmd="sleep 100", timeout=10.0, partial_stdout="", partial_stderr="")
    out = format_error_message(err)
    assert "Timeouts" in out


def test_exec_failed_synthesises_hint() -> None:
    result = ExecResult(stdout="", stderr="oops", exit_code=2)
    err = ExecFailed(result=result, argv_or_cmd="ls /nonexistent")
    out = format_error_message(err)
    assert "stderr" in out.lower() or "Logging" in out


def test_unsupported_strategy_synthesises_hint() -> None:
    err = UnsupportedStrategy(provider="daytona", strategy="head")
    out = format_error_message(err)
    assert "strategy" in out.lower()


def test_worktree_locked_synthesises_hint() -> None:
    err = WorktreeLocked(lock_path=Path("/tmp/lock"), holder_pid=12345)
    out = format_error_message(err)
    assert "Git worktree operation failed:" in out
    assert "12345" in out


def test_dirty_host_blocked_synthesises_hint() -> None:
    err = DirtyHostBlocked(host_repo_path=Path("/repo"), dirty_files=("a.py", "b.py"))
    out = format_error_message(err)
    assert "stash" in out or "allow_dirty" in out


def test_branch_exists_synthesises_hint() -> None:
    err = BranchExists(branch="eden/abc")
    out = format_error_message(err)
    assert "branch" in out.lower()


def test_git_command_failed_synthesises_hint() -> None:
    err = GitCommandFailed(argv=("git", "checkout"), exit_code=1, stderr="bad")
    out = format_error_message(err)
    assert "git" in out.lower()
