"""Verify prompt docs describe Eden's shell-block safety contract."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


def test_prompt_docs_keep_prompt_args_inert() -> None:
    docs = Path("docs/prompts.md").read_text(encoding="utf-8")
    assert "user-supplied `prompt_args` are substituted after shell-block expansion" in docs
    assert "Shell blocks that appear inside `prompt_args` values are not executed." in docs
