"""Verify snapshot/diff/apply for isolated provider patch-sync."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from eden.providers._impl.patch_sync import DiffResult, apply, diff, snapshot

pytestmark = pytest.mark.unit


def _w(p: Path, contents: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(contents, encoding="utf-8")


def test_snapshot_hashes_files(tmp_path: Path) -> None:
    _w(tmp_path / "a.txt", "alpha")
    _w(tmp_path / "sub" / "b.txt", "beta")
    snap = snapshot(tmp_path)
    assert set(snap.keys()) == {Path("a.txt"), Path("sub/b.txt")}
    snap2 = snapshot(tmp_path)
    assert snap == snap2


def test_snapshot_ignores_default_dirs(tmp_path: Path) -> None:
    _w(tmp_path / ".git" / "HEAD", "ref: refs/heads/main")
    _w(tmp_path / ".eden" / "logs" / "x.log", "log line")
    _w(tmp_path / "real.py", "import os")
    snap = snapshot(tmp_path)
    assert Path("real.py") in snap
    assert Path(".git/HEAD") not in snap
    assert Path(".eden/logs/x.log") not in snap


def test_snapshot_custom_ignore(tmp_path: Path) -> None:
    _w(tmp_path / "node_modules" / "x.js", "let a = 1")
    _w(tmp_path / "src" / "y.py", "x=2")
    snap = snapshot(tmp_path, ignore=("node_modules",))
    assert Path("src/y.py") in snap
    assert Path("node_modules/x.js") not in snap


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks require admin on Windows")
def test_snapshot_symlink_includes_target(tmp_path: Path) -> None:
    target = tmp_path / "real.txt"
    target.write_text("real", encoding="utf-8")
    link = tmp_path / "link.txt"
    os.symlink(target, link)
    snap = snapshot(tmp_path)
    assert Path("link.txt") in snap
    assert Path("real.txt") in snap
    other = tmp_path / "other.txt"
    other.write_text("other", encoding="utf-8")
    link.unlink()
    os.symlink(other, link)
    snap2 = snapshot(tmp_path)
    assert snap[Path("link.txt")] != snap2[Path("link.txt")]


def test_diff_classifies_changes() -> None:
    before = {Path("a"): "h1", Path("b"): "h2", Path("c"): "h3"}
    after = {Path("a"): "h1_new", Path("c"): "h3", Path("d"): "h4"}
    d = diff(before=before, after=after)
    assert d.added == frozenset({Path("d")})
    assert d.changed == frozenset({Path("a")})
    assert d.removed == frozenset({Path("b")})


def test_diff_empty_inputs() -> None:
    d = diff(before={}, after={})
    assert d.added == frozenset()
    assert d.changed == frozenset()
    assert d.removed == frozenset()


def test_apply_copies_added_and_changed(tmp_path: Path) -> None:
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    _w(src / "a.txt", "alpha-new")
    _w(src / "b.txt", "beta")
    _w(dst / "a.txt", "alpha-old")

    d = DiffResult(
        added=frozenset({Path("b.txt")}),
        changed=frozenset({Path("a.txt")}),
        removed=frozenset(),
    )
    fr = apply(d, src=src, dst=dst)
    assert fr.applied is True
    assert (dst / "a.txt").read_text() == "alpha-new"
    assert (dst / "b.txt").read_text() == "beta"
    assert set(fr.files_changed) == {Path("a.txt"), Path("b.txt")}
    assert fr.patch_size_bytes == len("alpha-new") + len("beta")


def test_apply_unlinks_removed(tmp_path: Path) -> None:
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    _w(dst / "gone.txt", "to be removed")
    d = DiffResult(
        added=frozenset(),
        changed=frozenset(),
        removed=frozenset({Path("gone.txt")}),
    )
    fr = apply(d, src=src, dst=dst)
    assert fr.applied is True
    assert not (dst / "gone.txt").exists()
    assert Path("gone.txt") in fr.files_changed


def test_apply_creates_parent_dirs(tmp_path: Path) -> None:
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    dst.mkdir()
    _w(src / "deep" / "nest" / "x.py", "x=1")
    d = DiffResult(
        added=frozenset({Path("deep/nest/x.py")}),
        changed=frozenset(),
        removed=frozenset(),
    )
    fr = apply(d, src=src, dst=dst)
    assert fr.applied is True
    assert (dst / "deep" / "nest" / "x.py").read_text() == "x=1"


def test_apply_partial_failure_marks_not_applied(tmp_path: Path) -> None:
    """A copy that fails (non-existent source) marks the whole result not-applied."""
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    dst.mkdir()
    d = DiffResult(
        added=frozenset({Path("phantom.txt")}),
        changed=frozenset(),
        removed=frozenset(),
    )
    fr = apply(d, src=src, dst=dst)
    assert fr.applied is False


def test_apply_unlink_missing_target_is_silent(tmp_path: Path) -> None:
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    dst.mkdir()
    d = DiffResult(
        added=frozenset(),
        changed=frozenset(),
        removed=frozenset({Path("ghost.txt")}),
    )
    fr = apply(d, src=src, dst=dst)
    assert fr.applied is True
