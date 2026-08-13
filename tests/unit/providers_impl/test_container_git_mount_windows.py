"""Verify the Windows linked-worktree git-mount fix.

Ported from Sandcastle's ADR 0006, unverified on a real Windows host +
Docker Desktop/Podman pairing (see container_git_mount_windows.py).
`plan_windows_git_mounts` is pure (no filesystem access) and genuinely
exercised here on any OS; the rest is exercised against a hand-written fake
``.git`` file, since a real Windows-style linked worktree can't be produced
by ``git worktree add`` on a non-Windows CI runner.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from eden.providers._impl.container import make_container_provider
from eden.providers._impl.container_git_mount_windows import (
    SANDBOX_PARENT_GIT_DIR,
    merge_windows_git_mounts,
    plan_windows_git_mounts,
    resolve_windows_git_mounts,
)
from eden.providers._impl.container_mounts import SANDBOX_WORKDIR
from eden.providers._types import BranchStrategy, CreateOptions, Mount
from eden.worktree._create import create_worktree
from tests.unit.providers.container.container_provider_helpers import find_run

pytestmark = pytest.mark.unit


def test_plan_windows_git_mounts_returns_none_for_posix_pointer() -> None:
    assert plan_windows_git_mounts("/repo/.git/worktrees/eden-abc") is None


def test_plan_windows_git_mounts_derives_parent_dir_and_gitfile_content() -> None:
    planned = plan_windows_git_mounts("C:\\Users\\me\\project\\.git\\worktrees\\eden-abc")
    assert planned == (
        "C:\\Users\\me\\project\\.git",
        f"gitdir: {SANDBOX_PARENT_GIT_DIR.as_posix()}/worktrees/eden-abc\n",
    )


def test_resolve_windows_git_mounts_matches_real_worktree_shape(tmp_git_repo: Path) -> None:
    """A worktree ``git worktree add`` creates on *this* host writes a
    pointer in *this* host's native shape: POSIX on Linux/macOS (not a
    Windows case — that's ``resolve_git_common_dir``'s job), genuinely
    Windows-shaped on Windows (where this function's real target case
    applies)."""
    handle = create_worktree(host_repo_path=tmp_git_repo, strategy=BranchStrategy.merge_to_head())
    try:
        mounts = resolve_windows_git_mounts(handle.worktree_path)
        if sys.platform == "win32":
            assert mounts is not None
        else:
            assert mounts is None
    finally:
        handle.close()


def _write_fake_windows_worktree(base: Path) -> Path:
    worktrees_dir = base / ".eden" / "worktrees"
    worktrees_dir.mkdir(parents=True)
    wt = worktrees_dir / "eden-abc"
    wt.mkdir()
    (wt / ".git").write_text(
        "gitdir: C:\\Users\\me\\project\\.git\\worktrees\\eden-abc\n", encoding="utf-8"
    )
    return wt


def test_resolve_windows_git_mounts_writes_corrected_gitfile(tmp_path: Path) -> None:
    wt = _write_fake_windows_worktree(tmp_path)

    mounts = resolve_windows_git_mounts(wt)

    assert mounts is not None
    parent_mount, gitfile_mount = mounts
    assert str(parent_mount.host) == "C:\\Users\\me\\project\\.git"
    assert parent_mount.sandbox == SANDBOX_PARENT_GIT_DIR
    assert gitfile_mount.sandbox == SANDBOX_WORKDIR / ".git"
    assert gitfile_mount.host == wt.parent / "eden-abc.git-windows"
    assert gitfile_mount.host.read_text(encoding="utf-8") == (
        f"gitdir: {SANDBOX_PARENT_GIT_DIR.as_posix()}/worktrees/eden-abc\n"
    )


def test_merge_windows_git_mounts_adds_to_map_and_returns_added(tmp_path: Path) -> None:
    wt = _write_fake_windows_worktree(tmp_path)
    mount_map = {SANDBOX_WORKDIR: Mount(host=wt, sandbox=SANDBOX_WORKDIR)}

    added = merge_windows_git_mounts(mount_map, wt)

    assert len(added) == 2
    assert mount_map[SANDBOX_PARENT_GIT_DIR] in added
    assert mount_map[SANDBOX_WORKDIR / ".git"] in added


def test_merge_windows_git_mounts_matches_real_worktree_shape(tmp_git_repo: Path) -> None:
    """Mirrors ``test_resolve_windows_git_mounts_matches_real_worktree_shape``
    at the ``merge_windows_git_mounts`` layer: a no-op on Linux/macOS (the
    real target case only exists on Windows)."""
    handle = create_worktree(host_repo_path=tmp_git_repo, strategy=BranchStrategy.merge_to_head())
    try:
        mount_map = {SANDBOX_WORKDIR: Mount(host=handle.worktree_path, sandbox=SANDBOX_WORKDIR)}
        added = merge_windows_git_mounts(mount_map, handle.worktree_path)
        if sys.platform == "win32":
            assert len(added) == 2
        else:
            assert added == frozenset()
            assert list(mount_map) == [SANDBOX_WORKDIR]
    finally:
        handle.close()


@pytest.mark.parametrize("binary", ["docker", "podman"])
def test_windows_linked_worktree_mounts_do_not_break_container_create(
    binary: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The Windows git-fix mounts must not trip the /home/agent-only
    file-mount-parent validation (``container_mounts._file_mount_parents``)
    — that check exists for arbitrary user file mounts and would otherwise
    raise ``MountConfigError`` for the ``/workspace/.git`` override, since
    its parent isn't under ``/home/agent``.
    """
    wt = _write_fake_windows_worktree(tmp_path)

    monkeypatch.setattr("eden.providers._impl.container.shutil.which", lambda _b: "/usr/bin/fake")
    captured: list[list[str]] = []

    def _run(cmd: list[str], *args: object, **kwargs: object) -> MagicMock:
        captured.append(list(cmd))
        m = MagicMock()
        m.returncode = 0
        m.stdout = "container-id\n"
        m.stderr = ""
        return m

    monkeypatch.setattr("eden.providers._impl.container.subprocess.run", _run)

    p = make_container_provider(binary=binary, image="alpine")  # type: ignore[arg-type]
    p.create(
        CreateOptions(
            branch="eden-abc",
            worktree_path=wt,
            host_repo_path=tmp_path,
            env={},
            mounts=(),
            name_hint="test",
        )
    )
    run_cmd = find_run(captured)
    argv_text = " ".join(run_cmd)
    # `_mount_argv` normalizes Windows-shaped sources to forward slashes for
    # `--mount type=bind,source=...` (drive-letter colon ambiguity) — assert
    # via `.as_posix()` rather than `str()` so this holds on a real Windows
    # runner too, where `str(WindowsPath(...))` would use backslashes.
    assert "C:/Users/me/project/.git" in argv_text
    assert (wt.parent / "eden-abc.git-windows").as_posix() in argv_text
