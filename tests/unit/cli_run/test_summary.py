"""Verify `eden run` completion summary output."""

from __future__ import annotations

import pytest

from eden.cli.run import _completion_summary

pytestmark = pytest.mark.unit


def test_completion_summary_reports_success() -> None:
    out = _completion_summary(completion_signal="<promise>COMPLETE</promise>", iterations=3)
    assert out == "Run complete: agent finished after 3 iteration(s)."


def test_completion_summary_reports_missing_signal() -> None:
    out = _completion_summary(completion_signal=None, iterations=3)
    assert out == "Run complete: reached 3 iteration(s) without completion signal."
