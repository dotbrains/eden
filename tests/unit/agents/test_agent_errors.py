"""Verify ``parse_stdout_error`` extracts agent error text from stdout."""

from __future__ import annotations

import pytest

from eden.agents._errors import parse_stdout_error

pytestmark = pytest.mark.unit


def test_returns_none_for_empty_stdout() -> None:
    assert parse_stdout_error("") is None


def test_returns_none_for_clean_text() -> None:
    assert parse_stdout_error("running task...\nall done\n") is None


def test_extracts_codex_pi_error_event() -> None:
    """Codex / Pi emit ``{"type": "error", "message": "..."}`` events."""
    stdout = '{"type":"info","message":"started"}\n{"type":"error","message":"rate limit hit"}\n'
    assert parse_stdout_error(stdout) == "rate limit hit"


def test_extracts_opencode_result_text() -> None:
    """OpenCode emits a final ``result`` event with ``is_error: true``."""
    stdout = '{"type":"result","is_error":true,"result":"workspace path is not writable"}\n'
    assert parse_stdout_error(stdout) == "workspace path is not writable"


def test_last_error_wins() -> None:
    """When stdout has multiple errors, the most recent one is returned."""
    stdout = (
        '{"type":"error","message":"first"}\n'
        '{"type":"info","message":"recovering"}\n'
        '{"type":"error","message":"second"}\n'
    )
    assert parse_stdout_error(stdout) == "second"


def test_extracts_plain_text_error_prefix() -> None:
    """Lines starting with ``Error:`` / ``Fatal:`` are picked up too."""
    assert (
        parse_stdout_error("starting\nError: connection refused\n") == "Error: connection refused"
    )
    assert parse_stdout_error("Fatal: out of memory\n") == "Fatal: out of memory"


def test_skips_unrecognised_json() -> None:
    stdout = '{"type":"text","content":"hi"}\n{"unrelated":"value"}\n'
    assert parse_stdout_error(stdout) is None


def test_skips_invalid_json() -> None:
    stdout = "{not valid json\nmore plain text\n"
    assert parse_stdout_error(stdout) is None


def test_falls_back_to_stringified_object_when_message_missing() -> None:
    """An ``error`` event without ``message`` still yields some context."""
    stdout = '{"type":"error","code":"E_RATE","detail":"slow down"}\n'
    # ``detail`` is recognised before falling back to ``str(obj)``.
    assert parse_stdout_error(stdout) == "slow down"


def test_falls_back_to_str_obj_when_no_known_field() -> None:
    stdout = '{"type":"error","code":"E_X"}\n'
    out = parse_stdout_error(stdout)
    assert out is not None
    assert "E_X" in out
