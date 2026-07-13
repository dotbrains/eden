"""Verify rewrite_paths walks JSON and replaces sandbox-prefix string starts."""

from __future__ import annotations

import json

import pytest

from eden.session._encode import rewrite_paths

pytestmark = pytest.mark.unit


def _r(line: str) -> str:
    return rewrite_paths(line, sandbox_prefix="/workspace", host_prefix="/host/repo")


def test_top_level_string_replaced() -> None:
    out = _r(json.dumps({"cwd": "/workspace"}))
    assert json.loads(out) == {"cwd": "/host/repo"}


def test_nested_string_replaced() -> None:
    obj = {"tool_input": {"file_path": "/workspace/src/x.py"}}
    out = _r(json.dumps(obj))
    assert json.loads(out) == {"tool_input": {"file_path": "/host/repo/src/x.py"}}


def test_array_of_strings_replaced() -> None:
    obj = {"paths": ["/workspace/a", "/elsewhere/b", "/workspace/c"]}
    out = _r(json.dumps(obj))
    assert json.loads(out) == {"paths": ["/host/repo/a", "/elsewhere/b", "/host/repo/c"]}


def test_substring_in_middle_not_replaced() -> None:
    """A path matching the prefix in the middle of a string is NOT replaced.

    rewrite_paths uses startswith, not contains.
    """
    obj = {"text": "see /workspace/x for details"}
    out = _r(json.dumps(obj))
    # The "see " prefix means startswith fails; line passes through unchanged.
    assert json.loads(out) == {"text": "see /workspace/x for details"}


def test_non_string_values_pass_through() -> None:
    obj = {"a": 1, "b": True, "c": None, "d": [1, 2, 3], "e": "/workspace/x"}
    out = _r(json.dumps(obj))
    assert json.loads(out) == {"a": 1, "b": True, "c": None, "d": [1, 2, 3], "e": "/host/repo/x"}


def test_invalid_json_returns_unchanged() -> None:
    assert _r("not json {") == "not json {"


def test_no_match_returns_equivalent_json() -> None:
    line = json.dumps({"k": "v"})
    out = _r(line)
    assert json.loads(out) == json.loads(line)


def test_exact_prefix_match_replaced() -> None:
    """A path equal to the sandbox prefix (no trailing slash) is also replaced."""
    out = _r(json.dumps({"cwd": "/workspace"}))
    assert json.loads(out) == {"cwd": "/host/repo"}
