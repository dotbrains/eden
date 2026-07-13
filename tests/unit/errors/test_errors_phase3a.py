"""Verify Phase 3a additions to the exception hierarchy."""

from __future__ import annotations

import builtins

import pytest

from eden.errors import (
    Aborted,
    ConfigError,
    CwdError,
    EdenError,
    EdenTimeoutError,
    EnvMergeError,
    HookError,
    HookFailed,
    HookTimeout,
    IdleTimeout,
    InvalidOptions,
    PromptError,
    StepTimeout,
)

pytestmark = pytest.mark.unit


def test_config_error_inherits_eden_error() -> None:
    assert issubclass(ConfigError, EdenError)


def test_invalid_options_carries_code_message_hint() -> None:
    err = InvalidOptions(
        code="config.invalid_options",
        message="must supply prompt or prompt_file",
        hint="provide one",
    )
    assert err.code == "config.invalid_options"
    assert err.message == "must supply prompt or prompt_file"
    assert err.hint == "provide one"
    assert "config.invalid_options" in str(err)


def test_invalid_options_inherits_config_error() -> None:
    assert issubclass(InvalidOptions, ConfigError)


def test_prompt_error_inherits_config_error() -> None:
    assert issubclass(PromptError, ConfigError)


def test_prompt_error_carries_cause() -> None:
    cause = ValueError("inner")
    err = PromptError(code="prompt.file_missing", message="x", cause=cause)
    assert err.cause is cause


def test_env_merge_error_inherits_config_error() -> None:
    assert issubclass(EnvMergeError, ConfigError)


def test_cwd_error_inherits_config_error() -> None:
    assert issubclass(CwdError, ConfigError)


def test_hook_error_inherits_eden_error() -> None:
    assert issubclass(HookError, EdenError)


def test_hook_failed_inherits_hook_error() -> None:
    assert issubclass(HookFailed, HookError)


def test_hook_timeout_inherits_hook_error() -> None:
    assert issubclass(HookTimeout, HookError)


def test_eden_timeout_error_subclasses_builtin_timeout_error() -> None:
    assert issubclass(EdenTimeoutError, EdenError)
    assert issubclass(EdenTimeoutError, builtins.TimeoutError)


def test_idle_timeout_inherits_eden_timeout_error() -> None:
    assert issubclass(IdleTimeout, EdenTimeoutError)


def test_step_timeout_inherits_eden_timeout_error() -> None:
    assert issubclass(StepTimeout, EdenTimeoutError)


def test_aborted_inherits_eden_error() -> None:
    assert issubclass(Aborted, EdenError)


def test_aborted_carries_reason() -> None:
    err = Aborted(reason="user-cancel")
    assert err.reason == "user-cancel"
    assert "user-cancel" in str(err)


def test_env_merge_error_default_code_and_str() -> None:
    err = EnvMergeError(message="conflict on FOO")
    assert err.code == "config.env_merge"
    assert err.message == "conflict on FOO"
    assert err.hint is None
    assert err.cause is None
    assert "[config.env_merge]" in str(err)


def test_cwd_error_default_code() -> None:
    err = CwdError(message="cwd does not exist")
    assert err.code == "config.cwd"
    assert "[config.cwd]" in str(err)


def test_hook_failed_default_code_and_str() -> None:
    err = HookFailed(message="pre-hook exited 1")
    assert err.code == "hook.failed"
    assert "[hook.failed]" in str(err)


def test_hook_timeout_default_code() -> None:
    err = HookTimeout(message="post-hook ran > 30s")
    assert err.code == "hook.timeout"
    assert "[hook.timeout]" in str(err)


def test_idle_timeout_default_code() -> None:
    err = IdleTimeout(message="no stdout for 60s")
    assert err.code == "timeout.idle"
    assert "[timeout.idle]" in str(err)


def test_step_timeout_default_code() -> None:
    err = StepTimeout(message="step exceeded budget")
    assert err.code == "timeout.step"
    assert "[timeout.step]" in str(err)
