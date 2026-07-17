"""Verify ``find_missing_keys`` + ``collect_missing_args`` semantics."""

from __future__ import annotations

import pytest

from eden.errors import PromptError
from eden.prompt._collect import collect_missing_args, find_missing_keys

pytestmark = pytest.mark.unit


def test_find_missing_keys_returns_unmapped() -> None:
    text = "hello {{NAME}} from {{PLACE}}"
    assert find_missing_keys(text, {}) == ("NAME", "PLACE")


def test_find_missing_keys_filters_supplied() -> None:
    text = "hello {{NAME}} from {{PLACE}}"
    assert find_missing_keys(text, {"NAME": "alice"}) == ("PLACE",)


def test_find_missing_keys_treats_none_as_missing() -> None:
    text = "hello {{NAME}} from {{PLACE}}"
    assert find_missing_keys(text, {"NAME": None, "PLACE": "Paris"}) == ("NAME",)


def test_find_missing_keys_skips_built_ins() -> None:
    """SOURCE_BRANCH and TARGET_BRANCH are injected by the orchestrator."""
    text = "branch={{SOURCE_BRANCH}} target={{TARGET_BRANCH}} task={{TASK}}"
    assert find_missing_keys(text, {}) == ("TASK",)


def test_find_missing_keys_deduplicates() -> None:
    """A key appearing twice is reported once, in first-appearance order."""
    text = "{{A}} {{B}} {{A}} {{B}}"
    assert find_missing_keys(text, {}) == ("A", "B")


def test_find_missing_keys_returns_empty_when_all_mapped() -> None:
    text = "{{A}} {{B}}"
    assert find_missing_keys(text, {"A": "1", "B": "2"}) == ()


def test_collect_missing_args_calls_prompt_fn_per_missing_key() -> None:
    calls: list[str] = []

    def fake(key: str) -> str:
        calls.append(key)
        return f"value-for-{key}"

    out = collect_missing_args("{{A}} {{B}}", {}, prompt_fn=fake)
    assert calls == ["A", "B"]
    assert out == {"A": "value-for-A", "B": "value-for-B"}


def test_collect_missing_args_preserves_existing() -> None:
    out = collect_missing_args(
        "{{A}} {{B}}",
        {"A": "pre"},
        prompt_fn=lambda k: f"v-{k}",
    )
    assert out == {"A": "pre", "B": "v-B"}


def test_collect_missing_args_replaces_none_values() -> None:
    out = collect_missing_args(
        "{{A}} {{B}}",
        {"A": None, "B": "pre"},
        prompt_fn=lambda k: f"v-{k}",
    )
    assert out == {"A": "v-A", "B": "pre"}


def test_collect_missing_args_rejects_non_string_existing_value() -> None:
    with pytest.raises(PromptError) as excinfo:
        collect_missing_args("{{A}}", {"A": 123}, prompt_fn=lambda k: f"v-{k}")
    assert excinfo.value.code == "prompt.invalid_arg"
    assert "A" in excinfo.value.message


def test_collect_missing_args_noop_when_nothing_missing() -> None:
    """No prompts when all keys supplied — and a fresh dict is returned."""
    args = {"A": "1"}
    out = collect_missing_args("{{A}}", args, prompt_fn=lambda k: "x")
    assert out == {"A": "1"}
    # Returned dict is a copy, not the caller's mapping.
    assert out is not args
