"""Verify {{KEY}} substitution + auto-injected built-ins."""

from __future__ import annotations

import pytest

from eden.errors import PromptError
from eden.prompt._render import render

pytestmark = pytest.mark.unit


def test_substitutes_user_key() -> None:
    out = render("Hi {{NAME}}!", args={"NAME": "Ada"}, source_branch="b", target_branch="main")
    assert out == "Hi Ada!"


def test_substitutes_key_with_inner_whitespace() -> None:
    out = render("Hi {{ NAME }}!", args={"NAME": "Ada"}, source_branch="b", target_branch="main")
    assert out == "Hi Ada!"


def test_unused_prompt_arg_warns() -> None:
    with pytest.warns(UserWarning, match="unused prompt_args keys: UNUSED"):
        out = render(
            "Hi {{NAME}}!",
            args={"NAME": "Ada", "UNUSED": "x"},
            source_branch="b",
            target_branch="main",
        )
    assert out == "Hi Ada!"


def test_substitutes_source_branch() -> None:
    out = render("on {{SOURCE_BRANCH}}", args={}, source_branch="feat/x", target_branch="main")
    assert out == "on feat/x"


def test_substitutes_target_branch() -> None:
    out = render("from {{TARGET_BRANCH}}", args={}, source_branch="b", target_branch="main")
    assert out == "from main"


def test_multiple_substitutions() -> None:
    out = render(
        "{{A}}-{{B}}-{{A}}", args={"A": "1", "B": "2"}, source_branch="x", target_branch="y"
    )
    assert out == "1-2-1"


def test_unknown_key_raises_prompt_error() -> None:
    with pytest.raises(PromptError) as excinfo:
        render("hello {{MISSING}}", args={"NAME": "Ada"}, source_branch="b", target_branch="main")
    assert excinfo.value.code == "prompt.unknown_key"
    assert "MISSING" in excinfo.value.message
    assert excinfo.value.hint is not None
    assert "NAME" in excinfo.value.hint
    assert "SOURCE_BRANCH" in excinfo.value.hint


def test_none_arg_value_raises_prompt_error() -> None:
    with pytest.raises(PromptError) as excinfo:
        render("hello {{NAME}}", args={"NAME": None}, source_branch="b", target_branch="main")
    assert excinfo.value.code == "prompt.missing_arg"
    assert "NAME" in excinfo.value.message


def test_scalar_arg_values_are_stringified() -> None:
    out = render(
        "{{COUNT}} {{RATIO}} {{ENABLED}}",
        args={"COUNT": 123, "RATIO": 1.5, "ENABLED": True},
        source_branch="b",
        target_branch="main",
    )
    assert out == "123 1.5 True"


def test_non_scalar_arg_value_raises_prompt_error() -> None:
    with pytest.raises(PromptError) as excinfo:
        render("hello {{NAME}}", args={"NAME": ["Ada"]}, source_branch="b", target_branch="main")
    assert excinfo.value.code == "prompt.invalid_arg"
    assert "NAME" in excinfo.value.message
    assert "list" in excinfo.value.message


def test_no_braces_returns_input() -> None:
    out = render("plain text", args={}, source_branch="b", target_branch="main")
    assert out == "plain text"


def test_single_brace_left_alone() -> None:
    out = render("a { b } c", args={}, source_branch="b", target_branch="main")
    assert out == "a { b } c"


def test_built_ins_cannot_be_overridden_by_args() -> None:
    """Args were already validated to not contain reserved keys (task 9), but
    render must defensively prefer built-ins anyway."""
    out = render(
        "{{SOURCE_BRANCH}}",
        args={"SOURCE_BRANCH": "evil"},
        source_branch="real",
        target_branch="main",
    )
    assert out == "real"
