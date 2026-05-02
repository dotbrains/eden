"""Verify Phase 4b additions to the exception hierarchy."""

from __future__ import annotations

import pytest

from eden.errors import (
    EdenError,
    RestAuthError,
    RestError,
    RestNotFoundError,
    RestRateLimited,
)

pytestmark = pytest.mark.unit


def test_rest_error_inherits_eden_error() -> None:
    assert issubclass(RestError, EdenError)


def test_rest_auth_error_inherits_rest_error() -> None:
    assert issubclass(RestAuthError, RestError)


def test_rest_not_found_inherits_rest_error() -> None:
    assert issubclass(RestNotFoundError, RestError)


def test_rest_rate_limited_inherits_rest_error() -> None:
    assert issubclass(RestRateLimited, RestError)


def test_rest_error_default_code_and_fields() -> None:
    err = RestError(message="boom", status=500, body="oops", url="https://x.test/y")
    assert err.code == "rest.error"
    assert err.message == "boom"
    assert err.hint is None
    assert err.cause is None
    assert err.status == 500
    assert err.body == "oops"
    assert err.url == "https://x.test/y"
    assert "[rest.error]" in str(err)


def test_rest_auth_error_default_code() -> None:
    err = RestAuthError(message="401 unauthorized", status=401, body="", url="https://x.test")
    assert err.code == "rest.auth"
    assert err.status == 401


def test_rest_not_found_default_code() -> None:
    err = RestNotFoundError(message="404", status=404, body="", url="https://x.test")
    assert err.code == "rest.not_found"


def test_rest_rate_limited_default_code() -> None:
    err = RestRateLimited(message="429", status=429, body="", url="https://x.test")
    assert err.code == "rest.rate_limited"


def test_rest_error_with_zero_status_for_connection_error() -> None:
    """status=0 indicates connection-level failure (no HTTP response at all)."""
    err = RestError(message="connection refused", status=0, url="https://x.test")
    assert err.status == 0


def test_rest_error_carries_cause() -> None:
    inner = ValueError("inner")
    err = RestError(message="x", cause=inner)
    assert err.cause is inner
