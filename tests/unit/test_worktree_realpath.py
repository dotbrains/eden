"""Tests that worktree paths get realpath'd before git ops.

Users who symlink their
``.eden/`` directory to another disk would otherwise see git's worktree
records mismatch their symlinked paths.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

from eden.providers._types import BranchStrategy
from eden.worktree._create import (
    _eden_dir,
    _lock_path_for,
    _worktree_path_for,
    create_worktree,
)

pytestmark = pytest.mark.unit

# Symlink tests are POSIX-only; Windows symlink semantics require admin /
# developer mode and we don't want flaky CI.
skip_on_windows = pytest.mark.skipif(
    sys.platform.startswith("win"), reason="symlink semantics differ on Windows"
)


def test_eden_dir_resolves_symlinks(tmp_path: Path) -> None:
    """When .eden is a symlink, _eden_dir returns the resolved target."""
    real_target = tmp_path / "actual-eden-state"
    real_target.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()
    symlink = repo / ".eden"
    if sys.platform.startswith("win"):
        pytest.skip("symlink semantics differ on Windows")
    symlink.symlink_to(real_target, target_is_directory=True)

    resolved = _eden_dir(repo)
    # The returned path should be the *real* target, not the symlink path.
    assert resolved == real_target.resolve()
    assert ".eden" not in resolved.parts  # symlink name dropped


def test_eden_dir_creates_dir_when_missing(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    assert not (repo / ".eden").exists()
    out = _eden_dir(repo)
    assert out.is_dir()
    assert out == (repo / ".eden").resolve()


def test_worktree_path_for_uses_resolved_eden(tmp_path: Path) -> None:
    if sys.platform.startswith("win"):
        pytest.skip("symlink semantics differ on Windows")
    real_target = tmp_path / "actual-eden-state"
    real_target.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".eden").symlink_to(real_target, target_is_directory=True)

    wt_path = _worktree_path_for(repo, "eden/foo")
    # Path should descend from the real target, not the symlink.
    assert wt_path.is_absolute()
    assert str(real_target.resolve()) in str(wt_path)
    assert "actual-eden-state" in wt_path.parts


def test_lock_path_for_uses_resolved_eden(tmp_path: Path) -> None:
    if sys.platform.startswith("win"):
        pytest.skip("symlink semantics differ on Windows")
    real_target = tmp_path / "actual-eden-state"
    real_target.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".eden").symlink_to(real_target, target_is_directory=True)

    lock_path = _lock_path_for(repo, branch="eden/foo")
    assert "actual-eden-state" in lock_path.parts


@skip_on_windows
def test_create_worktree_through_symlinked_eden(tmp_git_repo: Path) -> None:
    """End-to-end: create_worktree + close should work when .eden is a symlink."""
    # Move .eden contents into a separate dir and symlink them back.
    real_target = tmp_git_repo.parent / "eden-on-other-disk"
    real_target.mkdir()
    if (tmp_git_repo / ".eden").exists():
        shutil.rmtree(tmp_git_repo / ".eden")
    (tmp_git_repo / ".eden").symlink_to(real_target, target_is_directory=True)

    h = create_worktree(
        host_repo_path=tmp_git_repo,
        strategy=BranchStrategy.named("eden/symlinked"),
    )
    try:
        # Worktree should physically live under the real target.
        assert h.worktree_path.exists()
        assert "eden-on-other-disk" in h.worktree_path.parts
    finally:
        # Close should succeed — git's records and our path agree.
        result = h.close()
        assert result.action in ("removed", "preserved")


@skip_on_windows
def test_clean_resolves_symlinked_eden(tmp_path: Path) -> None:
    """`eden clean` should not be fooled by a symlinked .eden/."""
    from typer.testing import CliRunner

    from eden.cli.main import app

    real_target = tmp_path / "eden-on-other-disk"
    real_target.mkdir()
    (real_target / "logs").mkdir()
    (real_target / "logs" / "old.log").write_text("ancient")

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".eden").symlink_to(real_target, target_is_directory=True)

    # Backdate the log so --days 7 sweeps it.
    import os
    import time

    old = time.time() - (30 * 86400)
    os.utime(real_target / "logs" / "old.log", (old, old))

    runner = CliRunner()
    result = runner.invoke(app, ["clean", "--cwd", str(repo), "--days", "7"])
    assert result.exit_code == 0, result.stdout
    # The file lived under the realpath; it should be gone after clean.
    assert not (real_target / "logs" / "old.log").exists()
