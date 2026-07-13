"""Unit tests for structured-output extraction."""

from __future__ import annotations

import pytest

from eden.errors import StructuredOutputError
from eden.output import Output, extract_structured_output

pytestmark = pytest.mark.unit


def test_string_extracts_trimmed_contents() -> None:
    out = Output.string(tag="answer")
    result = extract_structured_output(
        "noise\n<answer>  hello world  </answer>\nmore",
        out,
        branch="b",
    )
    assert result == "hello world"


def test_string_missing_tag_raises() -> None:
    out = Output.string(tag="missing")
    with pytest.raises(StructuredOutputError) as ex:
        extract_structured_output("no tag here", out, branch="b")
    assert ex.value.tag == "missing"
    assert ex.value.raw_matched is None
    assert ex.value.branch == "b"


def test_string_returns_last_occurrence() -> None:
    out = Output.string(tag="t")
    result = extract_structured_output(
        "<t>first</t> middle <t>last</t>",
        out,
        branch="b",
    )
    assert result == "last"


def test_object_parses_json_and_validates() -> None:
    def schema(raw: object) -> dict[str, int]:
        if not isinstance(raw, dict):
            raise TypeError("expected object")
        return {"n": int(raw["n"])}

    out = Output.object(tag="result", schema=schema)
    result = extract_structured_output(
        '<result>{"n": 42}</result>',
        out,  # type: ignore[arg-type]
        branch="b",
    )
    assert result == {"n": 42}


def test_object_unwraps_json_fence() -> None:
    out = Output.object(tag="result", schema=lambda raw: raw)
    result = extract_structured_output(
        '<result>\n```json\n{"a": 1}\n```\n</result>',
        out,
        branch="b",
    )
    assert result == {"a": 1}


def test_object_unwraps_plain_fence() -> None:
    out = Output.object(tag="result", schema=lambda raw: raw)
    result = extract_structured_output(
        '<result>\n```\n{"a": 1}\n```\n</result>',
        out,
        branch="b",
    )
    assert result == {"a": 1}


def test_object_invalid_json_raises_with_cause() -> None:
    out = Output.object(tag="result", schema=lambda raw: raw)
    with pytest.raises(StructuredOutputError) as ex:
        extract_structured_output("<result>not json</result>", out, branch="b")
    assert ex.value.code == "output.invalid_json"
    assert ex.value.raw_matched == "not json"
    assert ex.value.cause is not None


def test_object_schema_failure_raises_validation_failed() -> None:
    def schema(raw: object) -> int:
        raise ValueError("nope")

    out = Output.object(tag="r", schema=schema)
    with pytest.raises(StructuredOutputError) as ex:
        extract_structured_output('<r>{"n": 1}</r>', out, branch="b")  # type: ignore[arg-type]
    assert ex.value.code == "output.validation_failed"
    assert isinstance(ex.value.cause, ValueError)


def test_unbalanced_open_tag_raises_missing() -> None:
    out = Output.string(tag="t")
    with pytest.raises(StructuredOutputError):
        extract_structured_output("<t>no close", out, branch="b")


def test_object_missing_tag_carries_branch_and_preserved() -> None:
    from pathlib import Path

    out = Output.object(tag="r", schema=lambda raw: raw)
    p = Path("/tmp/preserved")
    with pytest.raises(StructuredOutputError) as ex:
        extract_structured_output("nothing", out, branch="bb", preserved_worktree_path=p)
    assert ex.value.branch == "bb"
    assert ex.value.preserved_worktree_path == p


def test_missing_tag_carries_session_id_and_file_path() -> None:
    """Failed extraction surfaces session id."""
    from pathlib import Path

    out = Output.object(tag="r", schema=lambda raw: raw)
    p = Path("/tmp/sessions/iter-0-abc.jsonl")
    with pytest.raises(StructuredOutputError) as ex:
        extract_structured_output(
            "nothing",
            out,
            branch="bb",
            session_id="abc-123",
            session_file_path=p,
        )
    assert ex.value.session_id == "abc-123"
    assert ex.value.session_file_path == p


def test_invalid_json_carries_session_id() -> None:
    out = Output.object(tag="r", schema=lambda raw: raw)
    with pytest.raises(StructuredOutputError) as ex:
        extract_structured_output(
            "<r>{not json</r>",
            out,
            branch="b",
            session_id="sess-xyz",
        )
    assert ex.value.session_id == "sess-xyz"
    assert ex.value.code == "output.invalid_json"


def test_schema_failure_carries_session_id() -> None:
    def reject(_: object) -> object:
        raise ValueError("nope")

    out = Output.object(tag="r", schema=reject)
    with pytest.raises(StructuredOutputError) as ex:
        extract_structured_output(
            '<r>{"x": 1}</r>',
            out,
            branch="b",
            session_id="sess-1",
        )
    assert ex.value.session_id == "sess-1"
    assert ex.value.code == "output.validation_failed"


def test_string_missing_tag_carries_session_id() -> None:
    out = Output.string(tag="r")
    with pytest.raises(StructuredOutputError) as ex:
        extract_structured_output(
            "no tag here",
            out,
            branch="b",
            session_id="sess-str",
        )
    assert ex.value.session_id == "sess-str"


def test_session_fields_default_to_none() -> None:
    """Backward compat: callers that don't pass session args still work."""
    out = Output.object(tag="r", schema=lambda raw: raw)
    with pytest.raises(StructuredOutputError) as ex:
        extract_structured_output("nothing", out, branch="b")
    assert ex.value.session_id is None
    assert ex.value.session_file_path is None
