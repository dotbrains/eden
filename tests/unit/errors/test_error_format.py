"""Tests for the centralized error message formatter."""

from __future__ import annotations

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
from eden.worktree.errors import BranchExists

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
