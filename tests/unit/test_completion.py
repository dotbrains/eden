"""Verify completion-signal substring matcher."""

from __future__ import annotations

import pytest

from eden.orchestrator._completion import match

pytestmark = pytest.mark.unit


def test_string_signal_match_returns_signal() -> None:
    assert (
        match("done <promise>COMPLETE</promise>", "<promise>COMPLETE</promise>")
        == "<promise>COMPLETE</promise>"
    )


def test_string_signal_no_match_returns_none() -> None:
    assert match("just some text", "<promise>COMPLETE</promise>") is None


def test_list_signal_first_match_wins() -> None:
    assert match("FOO line", ["FOO", "BAR"]) == "FOO"
    assert match("BAR line", ["FOO", "BAR"]) == "BAR"


def test_list_signal_no_match() -> None:
    assert match("nothing", ["FOO", "BAR"]) is None


def test_empty_list_returns_none() -> None:
    assert match("anything", []) is None


def test_empty_string_in_list_skipped() -> None:
    assert match("anything", ["", "X"]) is None


def test_substring_not_word_boundary() -> None:
    """Substring match — 'DONE' inside 'DONEX' counts."""
    assert match("DONEX", "DONE") == "DONE"
