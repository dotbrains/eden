from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


def test_clone_tree_excludes_git_and_eden(tmp_path: Path) -> None:
    """``_clone_tree`` always excludes top-level .git and .eden directories."""
    from eden.sandboxes.isolated import _clone_tree

    src = tmp_path / "src"
    src.mkdir()
    (src / "code.py").write_text("x = 1\n")
    (src / ".git").mkdir()
    (src / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
    (src / ".eden").mkdir()
    (src / ".eden" / "log.txt").write_text("entry\n")
    (src / "src").mkdir()
    (src / "src" / "deep.py").write_text("y = 2\n")

    dst = tmp_path / "dst"
    _clone_tree(src, dst, timeout=None)

    assert (dst / "code.py").read_text() == "x = 1\n"
    assert (dst / "src" / "deep.py").read_text() == "y = 2\n"
    assert not (dst / ".git").exists()
    assert not (dst / ".eden").exists()


def test_clone_tree_fallback_when_cp_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Forcing the cp branch to fail still succeeds via copytree fallback."""
    import subprocess

    from eden.sandboxes import isolated as isolated_mod

    src = tmp_path / "src"
    src.mkdir()
    (src / "x.txt").write_text("hello\n")

    # Pretend we're on macOS so the cp branch is taken.
    monkeypatch.setattr(isolated_mod, "sys", type("S", (), {"platform": "darwin"}))

    def _run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        raise FileNotFoundError("simulated missing cp")

    monkeypatch.setattr("eden.sandboxes.isolated.subprocess.run", _run)

    dst = tmp_path / "dst"
    isolated_mod._clone_tree(src, dst, timeout=None)
    assert (dst / "x.txt").read_text() == "hello\n"


def test_clone_tree_timeout_raises_copy_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A ``cp -cR`` overrun raises ``CopyToWorktreeError(timed_out=True)``."""
    import subprocess

    from eden.errors import CopyToWorktreeError
    from eden.sandboxes import isolated as isolated_mod

    src = tmp_path / "src"
    src.mkdir()
    (src / "x.txt").write_text("hello\n")

    # Force the macOS cp branch.
    monkeypatch.setattr(isolated_mod, "sys", type("S", (), {"platform": "darwin"}))

    def _run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        raise subprocess.TimeoutExpired(cmd="cp", timeout=0.001)

    monkeypatch.setattr("eden.sandboxes.isolated.subprocess.run", _run)

    dst = tmp_path / "dst"
    with pytest.raises(CopyToWorktreeError) as excinfo:
        isolated_mod._clone_tree(src, dst, timeout=0.001)
    assert excinfo.value.timed_out is True
    assert excinfo.value.timeout == 0.001
    assert excinfo.value.source == src
    assert excinfo.value.target == dst
    # Partial dst was wiped on the timeout path.
    assert not dst.exists()


def test_clone_tree_copytree_oserror_raises_copy_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A ``shutil.copytree`` failure on the fallback path raises typed error."""
    import shutil as _shutil

    from eden.errors import CopyToWorktreeError
    from eden.sandboxes import isolated as isolated_mod

    src = tmp_path / "src"
    src.mkdir()
    (src / "x.txt").write_text("hello\n")
    dst = tmp_path / "dst"

    # Force the non-darwin path so we go straight to copytree.
    monkeypatch.setattr(isolated_mod, "sys", type("S", (), {"platform": "linux"}))

    def _copytree(*args: object, **kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(_shutil, "copytree", _copytree)

    with pytest.raises(CopyToWorktreeError) as excinfo:
        isolated_mod._clone_tree(src, dst, timeout=None)
    assert excinfo.value.timed_out is False
    assert "disk full" in str(excinfo.value)
