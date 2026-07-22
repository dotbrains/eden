"""Verify README quick-start env paths match Eden's scoped env loader."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


def test_readme_points_env_example_at_dot_eden_env() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "cp .eden/.env.example .eden/.env" in readme
    assert "cp .eden/.env.example .env" not in readme
