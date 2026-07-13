"""Verify PromptSource resolution: xor + file read + reserved-key validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from eden.errors import InvalidOptions, PromptError
from eden.prompt._source import resolve_source

pytestmark = pytest.mark.unit


def test_inline_prompt_returns_text() -> None:
    src = resolve_source(prompt="hello", prompt_file=None, prompt_args=None)
    assert src.text == "hello"
    assert src.is_literal is True


def test_file_prompt_reads_file(tmp_path: Path) -> None:
    f = tmp_path / "p.md"
    f.write_text("from file", encoding="utf-8")
    src = resolve_source(prompt=None, prompt_file=f, prompt_args=None)
    assert src.text == "from file"
    assert src.is_literal is False


def test_neither_supplied_raises_invalid_options() -> None:
    with pytest.raises(InvalidOptions) as excinfo:
        resolve_source(prompt=None, prompt_file=None, prompt_args=None)
    assert excinfo.value.code == "config.invalid_options"


def test_both_supplied_raises_invalid_options(tmp_path: Path) -> None:
    f = tmp_path / "p.md"
    f.write_text("x", encoding="utf-8")
    with pytest.raises(InvalidOptions) as excinfo:
        resolve_source(prompt="x", prompt_file=f, prompt_args=None)
    assert excinfo.value.code == "config.invalid_options"


def test_prompt_args_with_inline_raises_invalid_options() -> None:
    with pytest.raises(InvalidOptions) as excinfo:
        resolve_source(prompt="x", prompt_file=None, prompt_args={"K": "v"})
    assert "prompt_args" in excinfo.value.message


def test_prompt_args_reserved_keys_rejected(tmp_path: Path) -> None:
    f = tmp_path / "p.md"
    f.write_text("x", encoding="utf-8")
    with pytest.raises(InvalidOptions) as excinfo:
        resolve_source(
            prompt=None,
            prompt_file=f,
            prompt_args={"SOURCE_BRANCH": "x"},
        )
    assert "SOURCE_BRANCH" in excinfo.value.message


def test_missing_file_raises_prompt_error(tmp_path: Path) -> None:
    f = tmp_path / "missing.md"
    with pytest.raises(PromptError) as excinfo:
        resolve_source(prompt=None, prompt_file=f, prompt_args=None)
    assert excinfo.value.code == "prompt.file_missing"


def test_path_str_accepted(tmp_path: Path) -> None:
    f = tmp_path / "p.md"
    f.write_text("ok", encoding="utf-8")
    src = resolve_source(prompt=None, prompt_file=str(f), prompt_args=None)
    assert src.text == "ok"
    assert src.is_literal is False
