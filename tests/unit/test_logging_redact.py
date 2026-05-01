"""Verify secret redactor."""

from __future__ import annotations

import pytest

from eden.logging._redact import redact

pytestmark = pytest.mark.unit


def test_anthropic_key_redacted() -> None:
    out = redact("API key: sk-ant-abc123XYZ-DEF", env_values=())
    assert "sk-ant" not in out
    assert "<redacted>" in out


def test_github_pat_redacted() -> None:
    out = redact("token=ghp_AbCdEf012345", env_values=())
    assert "ghp_" not in out
    assert "<redacted>" in out


def test_slack_bot_token_redacted() -> None:
    out = redact("xoxb-123-456-abc", env_values=())
    assert "xoxb-" not in out
    assert "<redacted>" in out


def test_slack_user_token_redacted() -> None:
    out = redact("xoxp-secret-stuff", env_values=())
    assert "xoxp-" not in out
    assert "<redacted>" in out


def test_env_value_redacted() -> None:
    out = redact("password=mySecret123", env_values=("mySecret123",))
    assert "mySecret123" not in out
    assert "<redacted>" in out


def test_multiple_matches_one_line() -> None:
    out = redact("sk-ant-AAA and ghp_BBB on same line", env_values=())
    assert "sk-ant" not in out
    assert "ghp_" not in out
    assert out.count("<redacted>") == 2


def test_no_match_returns_input() -> None:
    out = redact("nothing sensitive here", env_values=())
    assert out == "nothing sensitive here"


def test_empty_env_value_skipped() -> None:
    out = redact("hello", env_values=("",))
    assert out == "hello"


def test_short_env_value_skipped() -> None:
    """Don't redact 1-2 char values to avoid mangling normal text."""
    out = redact("ab cd ef", env_values=("a", "ab"))
    assert out == "ab cd ef"
