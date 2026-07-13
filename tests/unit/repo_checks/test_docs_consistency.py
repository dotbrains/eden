"""Regression net: every public export is documented in the Python API docs."""

from __future__ import annotations

import re

import pytest

import eden
from tests.unit.repo_checks._paths import repo_root

pytestmark = pytest.mark.unit


def test_docs_python_api_covers_all_public_exports() -> None:
    docs_dir = repo_root() / "docs"
    api_docs = sorted(docs_dir.glob("python-api*.md"))
    assert docs_dir / "python-api.md" in api_docs

    text = "\n".join(path.read_text(encoding="utf-8") for path in api_docs)
    missing = [name for name in eden.__all__ if not re.search(rf"\b{re.escape(name)}\b", text)]
    assert missing == [], f"Python API docs missing: {missing}"
