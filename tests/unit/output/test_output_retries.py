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


def test_corrective_prompt_includes_previous_matched_output() -> None:
    out = Output.object(tag="result", schema=lambda d: d)
    exc = StructuredOutputError(
        code="output.invalid_json",
        message="tag <result> contains invalid JSON",
        tag="result",
        raw_matched="{bad",
        branch="b",
    )
    prompt = _corrective_output_prompt(out, exc, retries_remaining=2)
    assert "Retries remaining after this attempt: 2" in prompt
    assert "Previous matched output:" in prompt
    assert "{bad" in prompt
    assert "Do not change files" in prompt


def test_corrective_prompt_notes_missing_tag() -> None:
    out = Output.string(tag="answer")
    exc = StructuredOutputError(
        code="output.tag_missing",
        message="tag <answer> not found",
        tag="answer",
        raw_matched=None,
        branch="b",
    )
    prompt = _corrective_output_prompt(out, exc)
    assert "(no matching tag)" in prompt
