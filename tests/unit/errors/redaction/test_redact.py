"""Tests for eden._redact.redact_secrets."""

from __future__ import annotations

import pytest

from eden._redact import redact_secrets

pytestmark = pytest.mark.unit


def test_redacts_token_query_param() -> None:
    text = "curl 'https://x?token=abc123secret'"
    assert "abc123secret" not in redact_secrets(text)
    assert "token=<redacted>" in redact_secrets(text)


def test_redacts_authorization_bearer_header() -> None:
    text = "Authorization: Bearer sk-live-abc123"
    out = redact_secrets(text)
    assert "sk-live-abc123" not in out
    assert "Bearer <redacted>" in out


def test_redacts_password_equals() -> None:
    text = "password=my-secret-pass"
    out = redact_secrets(text)
    assert "my-secret-pass" not in out
    assert "password=<redacted>" in out


def test_preserves_non_secret_text() -> None:
    text = "hello world port=8080"
    assert redact_secrets(text) == text
