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


def test_openai_legacy_key_redacted() -> None:
    out = redact("OPENAI_API_KEY=sk-ABCDEFGHIJKLMNOPQRSTUVWX", env_values=())
    assert "sk-ABCDE" not in out
    assert "<redacted>" in out


def test_openai_project_key_redacted() -> None:
    out = redact("key=sk-proj-AbCdEf0123456789ABCDEF", env_values=())
    assert "sk-proj-" not in out
    assert "<redacted>" in out


def test_openai_short_placeholder_not_matched() -> None:
    """Placeholders like `sk-foo` shouldn't trip the OpenAI pattern."""
    out = redact("example: sk-foo", env_values=())
    assert out == "example: sk-foo"


def test_github_fine_grained_pat_redacted() -> None:
    out = redact("token=github_pat_11AAAAAA0123456789", env_values=())
    assert "github_pat_" not in out
    assert "<redacted>" in out


def test_github_oauth_token_redacted() -> None:
    out = redact("gho_abc123XYZ", env_values=())
    assert "gho_" not in out
    assert "<redacted>" in out


def test_github_server_token_redacted() -> None:
    out = redact("ghs_abc123XYZ", env_values=())
    assert "ghs_" not in out
    assert "<redacted>" in out


def test_aws_access_key_redacted() -> None:
    out = redact("AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE", env_values=())
    assert "AKIA" not in out
    assert "<redacted>" in out


def test_aws_short_match_not_matched() -> None:
    """AKIA followed by fewer than 16 chars is not a real key."""
    out = redact("AKIA1234", env_values=())
    assert out == "AKIA1234"


def test_stripe_live_secret_redacted() -> None:
    # Construct the prefix at runtime so GitHub's secret scanner doesn't
    # flag this fixture as a real Stripe key on push.
    fixture = "STRIPE=" + "sk_" + "live_" + "X" * 24
    out = redact(fixture, env_values=())
    assert "sk_" + "live_" not in out
    assert "<redacted>" in out


def test_stripe_test_key_not_redacted() -> None:
    """sk_test_ keys are public test fixtures; not secrets."""
    text = "STRIPE_TEST=" + "sk_" + "test_" + "X" * 24
    out = redact(text, env_values=())
    assert out == text
