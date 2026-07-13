from __future__ import annotations

from pathlib import Path

import pytest

from eden.providers._protocols import IsolatedSandboxHandle
from eden.providers._types import BranchStrategy, CreateOptions
from eden.sandboxes.isolated import provider as isolated_provider

pytestmark = pytest.mark.unit


def _opts(host: Path) -> CreateOptions:
    return CreateOptions(
        branch="HEAD",
        worktree_path=host,
        host_repo_path=host,
        env={},
        mounts=(),
        name_hint="test",
    )


def test_provider_kind_and_name() -> None:
    p = isolated_provider()
    assert p.kind == "isolated"
    assert p.name == "isolated"


def test_provider_supports_default_strategies() -> None:
    p = isolated_provider()
    assert p.supports_strategy(BranchStrategy.head())
    assert p.supports_strategy(BranchStrategy.merge_to_head())
    assert p.supports_strategy(BranchStrategy.named("x"))


def test_create_carves_isolated_root_with_copy(tmp_path: Path) -> None:
    host = tmp_path / "host"
    host.mkdir()
    (host / "src.py").write_text("x=1", encoding="utf-8")
    (host / "sub").mkdir()
    (host / "sub" / "y.txt").write_text("y", encoding="utf-8")

    p = isolated_provider()
    handle = p.create(_opts(host))
    try:
        assert handle.worktree_path != host
        assert handle.worktree_path.exists()
        assert (handle.worktree_path / "src.py").read_text() == "x=1"
        assert (handle.worktree_path / "sub" / "y.txt").read_text() == "y"
    finally:
        handle.close()


def test_create_handle_satisfies_isolated_protocol(tmp_path: Path) -> None:
    p = isolated_provider()
    handle = p.create(_opts(tmp_path))
    try:
        assert isinstance(handle, IsolatedSandboxHandle)
    finally:
        handle.close()


def test_close_removes_isolated_root(tmp_path: Path) -> None:
    p = isolated_provider()
    handle = p.create(_opts(tmp_path))
    isolated_root = handle.worktree_path
    assert isolated_root.exists()
    handle.close()
    assert not isolated_root.exists()


def test_close_is_idempotent(tmp_path: Path) -> None:
    p = isolated_provider()
    handle = p.create(_opts(tmp_path))
    handle.close()
    handle.close()  # must not raise


def test_finalize_replays_added_and_changed(tmp_path: Path) -> None:
    host = tmp_path / "host"
    host.mkdir()
    (host / "a.txt").write_text("alpha-orig", encoding="utf-8")
    (host / "b.txt").write_text("beta", encoding="utf-8")

    p = isolated_provider()
    handle = p.create(_opts(host))
    assert isinstance(handle, IsolatedSandboxHandle)
    try:
        # Modify the isolated copy
        (handle.worktree_path / "a.txt").write_text("alpha-new", encoding="utf-8")
        (handle.worktree_path / "c.txt").write_text("gamma", encoding="utf-8")
        (handle.worktree_path / "b.txt").unlink()

        fr = handle.finalize(target=host)
        assert fr.applied is True
        assert (host / "a.txt").read_text() == "alpha-new"
        assert (host / "c.txt").read_text() == "gamma"
        assert not (host / "b.txt").exists()
        assert set(fr.files_changed) == {Path("a.txt"), Path("b.txt"), Path("c.txt")}
    finally:
        handle.close()


def test_default_base_dir_is_under_eden_isolated(tmp_path: Path) -> None:
    host = tmp_path / "host"
    host.mkdir()
    p = isolated_provider()
    handle = p.create(_opts(host))
    try:
        assert (host / ".eden" / "isolated") in handle.worktree_path.parents
    finally:
        handle.close()


def test_explicit_base_dir(tmp_path: Path) -> None:
    host = tmp_path / "host"
    host.mkdir()
    custom = tmp_path / "custom_base"
    p = isolated_provider(base_dir=custom)
    handle = p.create(_opts(host))
    try:
        assert custom in handle.worktree_path.parents
    finally:
        handle.close()


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


def test_provider_accepts_copy_timeout_kwarg(tmp_path: Path) -> None:
    """``provider(copy_timeout=...)`` is accepted; default keeps existing behaviour."""
    p_default = isolated_provider()
    p_custom = isolated_provider(copy_timeout=120.0)
    p_disabled = isolated_provider(copy_timeout=None)
    assert p_default.kind == p_custom.kind == p_disabled.kind == "isolated"
