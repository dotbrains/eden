"""Tests for SandboxError retryable defaults."""

from __future__ import annotations

import pytest

from eden.providers._types import ExecResult
from eden.sandboxes.errors import (
    ContainerStartFailed,
    ContainerStartTimeout,
    ExecFailed,
    ExecTimeout,
    ImageNotFound,
    ImageUidMismatch,
    ProviderUnavailable,
)

pytestmark = pytest.mark.unit


def test_provider_unavailable_not_retryable() -> None:
    assert ProviderUnavailable(provider="x", binary="y").retryable is False


def test_image_not_found_not_retryable() -> None:
    assert ImageNotFound(image="img", stderr="").retryable is False


def test_container_start_failed_not_retryable() -> None:
    err = ContainerStartFailed(image="img", exit_code=1, stderr="")
    assert err.retryable is False


def test_exec_failed_not_retryable() -> None:
    result = ExecResult(stdout="", stderr="", exit_code=1)
    assert ExecFailed(result=result, argv_or_cmd="cmd").retryable is False


def test_exec_timeout_retryable() -> None:
    err = ExecTimeout(cmd="sleep", timeout=1.0, partial_stdout="", partial_stderr="")
    assert err.retryable is True


def test_container_start_timeout_retryable() -> None:
    err = ContainerStartTimeout(binary="docker", timeout=60.0)
    assert err.retryable is True


def test_image_uid_mismatch_not_retryable() -> None:
    err = ImageUidMismatch(image="img", image_uid=1000, expected_uid=1001)
    assert err.retryable is False
