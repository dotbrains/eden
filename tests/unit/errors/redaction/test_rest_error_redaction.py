"""Tests for RestError secret redaction and retryable flags."""

from __future__ import annotations

import pytest

from eden.errors import RestAuthError, RestError, RestNotFoundError, RestRateLimited

pytestmark = pytest.mark.unit


def test_rest_error_redacts_body_and_url() -> None:
    err = RestError(
        message="failed",
        body="token=secret-value",
        url="https://api.example.com?key=abc",
    )
    assert "secret-value" not in err.body
    assert "abc" not in err.url
    assert err.retryable is False


def test_rest_rate_limited_is_retryable() -> None:
    err = RestRateLimited(message="slow down", status=429)
    assert err.retryable is True


def test_rest_auth_not_retryable() -> None:
    err = RestAuthError(message="nope", status=401)
    assert err.retryable is False


def test_rest_not_found_not_retryable() -> None:
    err = RestNotFoundError(message="missing", status=404)
    assert err.retryable is False
