"""Tests for the centralized error message formatter."""

from __future__ import annotations

from pathlib import Path

import pytest

from eden import format_error_message
from eden.errors import (
    Aborted,
    AgentError,
    CopyToWorktreeError,
    CwdError,
    EnvMergeError,
    HookFailed,
    HookTimeout,
    IdleTimeout,
    InvalidOptions,
    PromptError,
    RestAuthError,
    RestError,
    RestNotFoundError,
    RestRateLimited,
    SessionCaptureFailed,
    StepTimeout,
    StructuredOutputError,
)
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
from eden.worktree.errors import (
    BranchExists,
    DirtyHostBlocked,
    GitCommandFailed,
    WorktreeLocked,
)

pytestmark = pytest.mark.unit


def test_format_invalid_options_includes_prefix_and_code() -> None:
    err = InvalidOptions(code="cfg.bad", message="oops", hint="check kwargs")
    out = format_error_message(err)
    assert "Configuration error:" in out
    assert "oops" in out
    assert "code: cfg.bad" in out
    assert "hint: check kwargs" in out


def test_format_preserves_existing_hint() -> None:
    err = PromptError(code="prompt.missing", message="no template", hint="touch .eden/prompt")
    out = format_error_message(err)
    assert "Prompt resolution failed:" in out
    assert "hint: touch .eden/prompt" in out


def test_format_cwd_error() -> None:
    err = CwdError(message="not a git repo")
    out = format_error_message(err)
    assert "Invalid working directory:" in out
    assert "not a git repo" in out


def test_format_env_merge_error() -> None:
    err = EnvMergeError(message="conflict on FOO", hint="rename your variable")
    out = format_error_message(err)
    assert "Environment merge failed:" in out
    assert "rename your variable" in out


def test_format_step_timeout_inherits_kind_prefix() -> None:
    err = StepTimeout(message="iteration > 600s")
    out = format_error_message(err)
    assert "Iteration step timed out:" in out


def test_format_idle_timeout_inherits_kind_prefix() -> None:
    err = IdleTimeout(message="no stdout for 60s")
    out = format_error_message(err)
    assert "Agent went idle:" in out


def test_format_rest_subclasses() -> None:
    auth = RestAuthError(message="401 unauthorized")
    assert "Authentication failed:" in format_error_message(auth)
    nf = RestNotFoundError(message="404 sandbox missing")
    assert "Resource not found:" in format_error_message(nf)
    rl = RestRateLimited(message="429 rate limit")
    assert "Rate limit hit:" in format_error_message(rl)
    base = RestError(message="500 server error")
    assert "REST request failed:" in format_error_message(base)


def test_format_hook_failure() -> None:
    err = HookFailed(message="exit 1")
    assert "Hook failed:" in format_error_message(err)
    timed = HookTimeout(message="exceeded 30s")
    assert "Hook failed:" in format_error_message(timed)


def test_format_agent_error() -> None:
    err = AgentError(
        message="agent failed",
        agent_name="claude-code",
        exit_code=2,
        stderr="oops",
    )
    out = format_error_message(err)
    assert "Agent invocation failed:" in out
    assert "agent failed" in out


def test_format_structured_output_error() -> None:
    err = StructuredOutputError(
        message="tag <result> missing",
        tag="result",
        raw_matched=None,
        branch="eden/abc",
    )
    out = format_error_message(err)
    assert "Structured output extraction failed:" in out


def test_format_copy_to_worktree_error() -> None:
    err = CopyToWorktreeError(message="copy timed out", timed_out=True, timeout=120.0)
    out = format_error_message(err)
    assert "Worktree copy failed:" in out


def test_format_session_capture_failed() -> None:
    err = SessionCaptureFailed(message="no jsonl found")
    assert "Session capture failed:" in format_error_message(err)


def test_format_aborted() -> None:
    err = Aborted(reason="user-ctrl-c")
    out = format_error_message(err)
    assert "Aborted:" in out


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


def test_format_rejects_non_eden_errors() -> None:
    with pytest.raises(TypeError):
        format_error_message(ValueError("not an eden error"))  # type: ignore[arg-type]


def test_format_uses_code_attribute_when_present() -> None:
    err = InvalidOptions(code="x.y.z", message="msg")
    assert "code: x.y.z" in format_error_message(err)


def test_format_falls_back_to_class_name_when_no_code() -> None:
    # Sandbox / worktree errors don't carry `code`.
    err = BranchExists(branch="main")
    out = format_error_message(err)
    assert "code: BranchExists" in out
