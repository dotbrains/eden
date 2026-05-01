"""Verify Phase 3b additions to the exception hierarchy."""

from __future__ import annotations

import pytest

from eden.errors import EdenError, SessionCaptureFailed

pytestmark = pytest.mark.unit


def test_session_capture_failed_inherits_eden_error() -> None:
    assert issubclass(SessionCaptureFailed, EdenError)


def test_session_capture_failed_default_code() -> None:
    err = SessionCaptureFailed(message="not found")
    assert err.code == "session.capture_failed"
    assert err.message == "not found"
    assert err.hint is None
    assert err.cause is None
    assert "[session.capture_failed]" in str(err)


def test_session_capture_failed_carries_cause() -> None:
    cause = FileNotFoundError("missing")
    err = SessionCaptureFailed(message="x", cause=cause)
    assert err.cause is cause
