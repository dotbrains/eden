"""Unit tests for structured-output retry config + corrective-prompt builder."""

from __future__ import annotations

import pytest

from eden.errors import StructuredOutputError
from eden.orchestrator import _corrective_output_prompt
from eden.output import Output

pytestmark = pytest.mark.unit


def test_max_retries_defaults_to_zero() -> None:
    assert Output.object(tag="r", schema=lambda d: d).max_retries == 0
    assert Output.string(tag="r").max_retries == 0


def test_max_retries_is_stored() -> None:
    assert Output.object(tag="r", schema=lambda d: d, max_retries=3).max_retries == 3
    assert Output.string(tag="r", max_retries=2).max_retries == 2


def test_corrective_prompt_quotes_failure_and_restates_tag() -> None:
    out = Output.object(tag="result", schema=lambda d: d)
    exc = StructuredOutputError(
        code="output.invalid_json",
        message="tag <result> contains invalid JSON",
        tag="result",
        raw_matched="{bad",
        branch="b",
        cause=ValueError("Expecting value"),
    )
    prompt = _corrective_output_prompt(out, exc)
    assert "<result>" in prompt
    assert "</result>" in prompt
    assert "invalid JSON" in prompt
    assert "Expecting value" in prompt  # cause detail surfaced
