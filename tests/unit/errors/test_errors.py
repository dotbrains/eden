"""Verify the Phase 2 exception hierarchy."""

from __future__ import annotations

from pathlib import Path

import pytest

from eden.errors import EdenError
from eden.providers._types import ExecResult
from eden.sandboxes.errors import (
    ContainerStartFailed,
    ContainerStartTimeout,
    ExecFailed,
    ExecTimeout,
    ImageNotFound,
    MountConfigError,
    ProviderUnavailable,
    SandboxError,
    UnsupportedStrategy,
)
from eden.worktree.errors import (
    BranchExists,
    DirtyHostBlocked,
    GitCommandFailed,
    WorktreeError,
    WorktreeLocked,
)

pytestmark = pytest.mark.unit


def test_eden_error_is_exception() -> None:
    assert issubclass(EdenError, Exception)


def test_worktree_error_inherits_eden_error() -> None:
    assert issubclass(WorktreeError, EdenError)


def test_sandbox_error_inherits_eden_error() -> None:
    assert issubclass(SandboxError, EdenError)


def test_worktree_locked_carries_path_and_pid() -> None:
    err = WorktreeLocked(lock_path=Path("/tmp/x.lock"), holder_pid=4242)
    assert err.lock_path == Path("/tmp/x.lock")
    assert err.holder_pid == 4242
    assert "4242" in str(err)


def test_dirty_host_blocked_carries_path_and_files() -> None:
    err = DirtyHostBlocked(host_repo_path=Path("/repo"), dirty_files=("a.py", "b.py"))
    assert err.host_repo_path == Path("/repo")
    assert err.dirty_files == ("a.py", "b.py")
    assert "a.py" in str(err)


def test_branch_exists_carries_branch() -> None:
    err = BranchExists(branch="feat/x")
    assert err.branch == "feat/x"
    assert "feat/x" in str(err)


def test_git_command_failed_carries_argv_and_stderr() -> None:
    err = GitCommandFailed(argv=("git", "status"), exit_code=128, stderr="boom")
    assert err.argv == ("git", "status")
    assert err.exit_code == 128
    assert err.stderr == "boom"
    assert "128" in str(err)


def test_provider_unavailable_carries_provider_and_binary() -> None:
    err = ProviderUnavailable(provider="docker", binary="docker")
    assert err.provider == "docker"
    assert err.binary == "docker"


def test_image_not_found_carries_image_and_stderr() -> None:
    err = ImageNotFound(image="alpine:latest", stderr="not found")
    assert err.image == "alpine:latest"
    assert err.stderr == "not found"


def test_container_start_failed_carries_image_exit_stderr() -> None:
    err = ContainerStartFailed(image="alpine", exit_code=125, stderr="boom")
    assert err.exit_code == 125


def test_exec_failed_carries_result_and_cmd() -> None:
    result = ExecResult(stdout="", stderr="bad", exit_code=2)
    err = ExecFailed(result=result, argv_or_cmd="ls /missing")
    assert err.result is result
    assert err.argv_or_cmd == "ls /missing"


def test_exec_timeout_carries_partial_buffers() -> None:
    err = ExecTimeout(
        cmd="sleep 100",
        timeout=1.0,
        partial_stdout="hello",
        partial_stderr="warn",
    )
    assert err.timeout == 1.0
    assert err.partial_stdout == "hello"
    assert err.partial_stderr == "warn"


def test_container_start_timeout_carries_binary_and_timeout() -> None:
    err = ContainerStartTimeout(binary="docker", timeout=120.0)
    assert err.binary == "docker"
    assert err.timeout == 120.0
    assert isinstance(err, SandboxError)


def test_mount_config_error_carries_paths() -> None:
    err = MountConfigError(
        sandbox_path="/etc/foo/bar.conf",
        parent="/etc/foo",
        sandbox_homedir="/home/agent",
    )
    assert err.sandbox_path == "/etc/foo/bar.conf"
    assert err.parent == "/etc/foo"
    assert err.sandbox_homedir == "/home/agent"
    assert "/etc/foo" in str(err)


def test_unsupported_strategy_carries_provider_and_tag() -> None:
    err = UnsupportedStrategy(provider="docker", strategy="head")
    assert err.provider == "docker"
    assert err.strategy == "head"
