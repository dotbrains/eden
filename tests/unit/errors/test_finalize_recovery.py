"""Verify ``format_finalize_recovery`` produces a copy-pastable rsync hint."""

from __future__ import annotations

import shlex
from pathlib import Path

import pytest

from eden.orchestrator.finalize._finalize_recovery import format_finalize_recovery

pytestmark = pytest.mark.unit


def test_hard_failure_includes_error_and_rsync(tmp_path: Path) -> None:
    iso = tmp_path / "iso"
    tgt = tmp_path / "tgt"
    out = format_finalize_recovery(
        isolated_path=iso,
        target_path=tgt,
        error=RuntimeError("boom"),
    )
    assert "boom" in out
    assert str(iso) in out
    assert str(tgt) in out
    # Recovery commands present when preserved=True (default).
    iso_q = shlex.quote(str(iso))
    tgt_q = shlex.quote(str(tgt))
    assert f"rsync -a --exclude=.git --exclude=.eden {iso_q}/ {tgt_q}/" in out
    assert f"rm -rf {iso_q}" in out


def test_soft_failure_lists_files(tmp_path: Path) -> None:
    foo = Path("src/foo.py")
    bar = Path("src/bar.py")
    out = format_finalize_recovery(
        isolated_path=tmp_path / "iso",
        target_path=tmp_path / "tgt",
        files_failed=(foo, bar),
    )
    # No error line when error is None.
    assert "error:" not in out
    # Use ``str(path)`` so the assertion matches the OS-native separator
    # (Windows: backslashes; POSIX: forward slashes) — the formatter renders
    # paths via ``f"{path}"`` which is platform-native.
    assert str(foo) in out
    assert str(bar) in out


def test_preserved_false_omits_recovery_commands(tmp_path: Path) -> None:
    out = format_finalize_recovery(
        isolated_path=tmp_path / "iso",
        target_path=tmp_path / "tgt",
        error=RuntimeError("boom"),
        preserved=False,
    )
    assert "rsync" not in out
    assert "rm -rf" not in out
    # Diagnostic header still emitted.
    assert "boom" in out


def test_quotes_paths_with_spaces(tmp_path: Path) -> None:
    iso = tmp_path / "Foo Bar" / "iso"
    tgt = tmp_path / "Baz Qux" / "tgt"
    out = format_finalize_recovery(
        isolated_path=iso,
        target_path=tgt,
        error=RuntimeError("boom"),
    )
    # shlex.quote wraps each path so the rsync command survives a paste.
    assert shlex.quote(str(iso)) in out
    assert shlex.quote(str(tgt)) in out


def test_no_files_section_when_files_failed_empty(tmp_path: Path) -> None:
    out = format_finalize_recovery(
        isolated_path=tmp_path / "iso",
        target_path=tmp_path / "tgt",
        files_failed=(),
    )
    assert "files:" not in out
