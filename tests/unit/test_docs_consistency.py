"""Regression net: every public export is documented in docs/python-api.md."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import eden

pytestmark = pytest.mark.unit


def test_docs_python_api_covers_all_public_exports() -> None:
    api_doc = Path(__file__).resolve().parents[2] / "docs" / "python-api.md"
    text = api_doc.read_text(encoding="utf-8")
    missing = [name for name in eden.__all__ if not re.search(rf"\b{re.escape(name)}\b", text)]
    assert missing == [], f"docs/python-api.md missing: {missing}"
