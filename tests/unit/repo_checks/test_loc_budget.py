"""Verify LOC budget path matching."""

from __future__ import annotations

from pathlib import Path

from scripts.check_loc_budget import _matches


def test_recursive_file_patterns_match_direct_and_nested_files() -> None:
    assert _matches(Path("eden/errors.py"), "eden/**/*.py")
    assert _matches(Path("eden/orchestrator/loop/_run_loop.py"), "eden/**/*.py")
    assert _matches(Path("tests/test_version.py"), "tests/**/*.py")
    assert _matches(Path("tests/unit/cli/test_cli_init.py"), "tests/**/*.py")
    assert not _matches(Path("docs/development.md"), "tests/**/*.py")


def test_recursive_directory_excludes_match_nested_paths() -> None:
    assert _matches(Path("docs/superpowers/plans/archive.md"), "docs/superpowers/**")
    assert not _matches(Path("docs/development.md"), "docs/superpowers/**")
