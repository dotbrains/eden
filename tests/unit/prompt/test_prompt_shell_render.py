"""Verify public render_prompt shell-block ordering."""

from __future__ import annotations

from pathlib import Path

import pytest

from eden.prompt import render_prompt
from eden.providers._types import ExecResult

from ._shell_helpers import FakeHandle

pytestmark = pytest.mark.unit


def test_render_prompt_full_pipeline(tmp_path: Path) -> None:
    """Public render_prompt: substitution + shell expansion in order."""
    h = FakeHandle({"date": ExecResult(stdout="2026-05-01\n", stderr="", exit_code=0)})
    out = render_prompt(
        text="branch={{SOURCE_BRANCH}} date=!`date`",
        args={},
        source_branch="feat/x",
        target_branch="main",
        handle=h,
    )
    assert out == "branch=feat/x date=2026-05-01"


def test_render_prompt_built_ins_inside_shell_block() -> None:
    """``{{SOURCE_BRANCH}}`` substitutes inside a shell-block body."""
    h = FakeHandle({"git log feat/x": ExecResult(stdout="abc123\n", stderr="", exit_code=0)})
    out = render_prompt(
        text="!`git log {{SOURCE_BRANCH}}`",
        args={},
        source_branch="feat/x",
        target_branch="main",
        handle=h,
    )
    assert out == "abc123"
    assert h.calls == ["git log feat/x"]


def test_render_prompt_shell_block_in_arg_value_is_inert() -> None:
    """Arg values containing ``!`...``` text must NOT trigger shell exec."""
    h = FakeHandle({})
    out = render_prompt(
        text="user={{USER_INPUT}}",
        args={"USER_INPUT": "!`rm -rf /`"},
        source_branch="b",
        target_branch="main",
        handle=h,
    )
    # Arg substituted verbatim; no shell-block expansion ran on its value.
    assert out == "user=!`rm -rf /`"
    assert h.calls == []


def test_render_prompt_shell_block_then_arg_substitution() -> None:
    """Shell expansion runs on the raw template; args substitute afterwards."""
    h = FakeHandle({"date": ExecResult(stdout="2026-05-01\n", stderr="", exit_code=0)})
    out = render_prompt(
        text="who={{NAME}} when=!`date`",
        args={"NAME": "ada"},
        source_branch="b",
        target_branch="main",
        handle=h,
    )
    assert out == "who=ada when=2026-05-01"
