"""Unit tests for structured-output error metadata."""

from __future__ import annotations

from pathlib import Path

import pytest

from eden._types import Commit
from eden.errors import StructuredOutputError
from eden.output import Output, extract_structured_output

pytestmark = pytest.mark.unit


def test_object_missing_tag_carries_branch_and_preserved() -> None:
    out = Output.object(tag="r", schema=lambda raw: raw)
    preserved_path = Path("/tmp/preserved")
    with pytest.raises(StructuredOutputError) as ex:
        extract_structured_output(
            "nothing", out, branch="bb", preserved_worktree_path=preserved_path
        )
    assert ex.value.branch == "bb"
    assert ex.value.preserved_worktree_path == preserved_path


def test_missing_tag_carries_commits() -> None:
    out = Output.object(tag="r", schema=lambda raw: raw)
    commits = [Commit(sha="abc123"), Commit(sha="def456")]
    with pytest.raises(StructuredOutputError) as ex:
        extract_structured_output("nothing", out, branch="bb", commits=commits)
    assert ex.value.commits == commits


def test_missing_tag_carries_session_id_and_file_path() -> None:
    out = Output.object(tag="r", schema=lambda raw: raw)
    session_path = Path("/tmp/sessions/iter-0-abc.jsonl")
    with pytest.raises(StructuredOutputError) as ex:
        extract_structured_output(
            "nothing",
            out,
            branch="bb",
            session_id="abc-123",
            session_file_path=session_path,
        )
    assert ex.value.session_id == "abc-123"
    assert ex.value.session_file_path == session_path


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
    out = Output.object(tag="r", schema=lambda raw: raw)
    with pytest.raises(StructuredOutputError) as ex:
        extract_structured_output("nothing", out, branch="b")
    assert ex.value.session_id is None
    assert ex.value.session_file_path is None
