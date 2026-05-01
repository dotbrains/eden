"""Verify the package exposes a version string and it matches pyproject.toml."""

from __future__ import annotations

import tomllib
from pathlib import Path

import eden


def test_version_string_exists() -> None:
    assert isinstance(eden.__version__, str)
    assert eden.__version__  # non-empty


def test_version_matches_pyproject() -> None:
    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    with pyproject.open("rb") as fh:
        data = tomllib.load(fh)
    declared = data["project"]["version"]
    assert eden.__version__ == declared, (
        f"eden.__version__ ({eden.__version__!r}) does not match "
        f"pyproject.toml project.version ({declared!r})"
    )
