"""Verify the run-summary formatters."""

from __future__ import annotations

import pytest

from eden._types import Usage
from eden.orchestrator._summary import context_window_k, format_context_window_line

pytestmark = pytest.mark.unit


def _u(input_t: int, cc: int = 0, cr: int = 0, output: int = 0) -> Usage:
    return Usage(
        input_tokens=input_t,
        cache_creation_input_tokens=cc,
        cache_read_input_tokens=cr,
        output_tokens=output,
    )


def test_zero_input_returns_zero_k() -> None:
    assert context_window_k(_u(0)) == 0
    assert format_context_window_line(_u(0)) == "Context window: 0k"


def test_sums_input_cache_creation_and_cache_read() -> None:
    assert context_window_k(_u(50_000, cc=20_000, cr=30_000)) == 100


def test_rounds_up_to_nearest_1000() -> None:
    assert context_window_k(_u(1)) == 1
    assert context_window_k(_u(1001)) == 2
    assert context_window_k(_u(999)) == 1
    assert context_window_k(_u(50_500)) == 51


def test_output_tokens_excluded() -> None:
    """Output tokens are not part of the next-call context window."""
    assert context_window_k(_u(50_000, output=999_999)) == 50


def test_format_line_shape() -> None:
    assert format_context_window_line(_u(50_000)) == "Context window: 50k"
    assert (
        format_context_window_line(_u(99_999, cc=1, cr=0, output=0))
        == "Context window: 100k"
    )
