"""Verify git-common-dir resolution and mounting for linked worktrees."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from eden.providers._impl.container import make_container_provider
from eden.providers._impl.container_git_mount import resolve_git_common_dir
from eden.providers._types import BranchStrategy, CreateOptions
from eden.worktree._create import create_worktree
from tests.unit.providers.container.container_provider_helpers import find_run, skip_on_windows

pytestmark = pytest.mark.unit


def test_head_strategy_needs_no_extra_mount(tmp_git_repo: Path) -> None:
    """``.git`` is a real directory when worktree_path == host_repo_path."""
    assert resolve_git_common_dir(tmp_git_repo) is None


def test_non_git_directory_needs_no_extra_mount(tmp_path: Path) -> None:
    assert resolve_git_common_dir(tmp_path) is None


def test_missing_directory_needs_no_extra_mount(tmp_path: Path) -> None:
    assert resolve_git_common_dir(tmp_path / "does-not-exist") is None


def test_linked_worktree_resolves_common_git_dir(tmp_git_repo: Path) -> None:
    """merge_to_head/named strategies carve a linked worktree whose ``.git``
    is a file pointing at the main repo's git dir — that dir must be
    bind-mounted too, or git commands inside the container fail with
    ``fatal: not a git repository``. On Windows the resolver intentionally
    returns ``None`` instead (see module docstring): the ``.git`` file's own
    ``gitdir:`` content is a Windows path a Linux container can't parse
    regardless of mount layout.
    """
    handle = create_worktree(host_repo_path=tmp_git_repo, strategy=BranchStrategy.merge_to_head())
    try:
        assert (handle.worktree_path / ".git").is_file()
        expected = None if sys.platform == "win32" else (tmp_git_repo / ".git").resolve()
        assert resolve_git_common_dir(handle.worktree_path) == expected
    finally:
        handle.close()


@skip_on_windows
@pytest.mark.parametrize("binary", ["docker", "podman"])
def test_linked_worktree_git_common_dir_is_mounted(
    binary: str, tmp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Carve the worktree with the real `git worktree add` *before* patching
    # `subprocess.run` — `eden.providers._impl.container.subprocess` is the
    # `subprocess` module itself, so patching its `run` attribute is global,
    # and would otherwise no-op the git worktree creation this test relies on.
    handle = create_worktree(host_repo_path=tmp_git_repo, strategy=BranchStrategy.merge_to_head())
    try:
        monkeypatch.setattr(
            "eden.providers._impl.container.shutil.which", lambda _b: "/usr/bin/fake"
        )
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
                branch=handle.branch,
                worktree_path=handle.worktree_path,
                host_repo_path=tmp_git_repo,
                env={},
                mounts=(),
                name_hint="test",
            )
        )
        run_cmd = find_run(captured)
        bind_specs = [run_cmd[i + 1] for i, a in enumerate(run_cmd) if a == "-v"]
        common_dir = (tmp_git_repo / ".git").resolve()
        assert any(spec.startswith(f"{common_dir}:{common_dir}:") for spec in bind_specs), (
            bind_specs
        )
    finally:
        handle.close()
