"""Path helpers for repository self-check tests."""

from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").is_file() and (parent / "action.yml").is_file():
            return parent
    raise RuntimeError("could not locate repository root")
