"""Verify host-side git subprocess calls bound by a deadline."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from eden.worktree._git import _DEFAULT_GIT_TIMEOUT, _run_git, branch_exists
from eden.worktree.errors import GitCommandFailed, GitCommandTimeout

pytestmark = pytest.mark.unit


def _raise_timeout(*args: Any, **kwargs: Any) -> None:
    raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs.get("timeout", 0))


def test_default_timeout_is_60s() -> None:
    assert _DEFAULT_GIT_TIMEOUT == 60.0


def test_run_git_passes_timeout_to_subprocess(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: dict[str, Any] = {}

    def _fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured.update(kwargs)
        return subprocess.CompletedProcess(args[0], 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)
    _run_git(("git", "status"), cwd=tmp_path)
    assert captured["timeout"] == _DEFAULT_GIT_TIMEOUT


def test_run_git_override_timeout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    captured: dict[str, Any] = {}

    def _fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured.update(kwargs)
        return subprocess.CompletedProcess(args[0], 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)
    _run_git(("git", "status"), cwd=tmp_path, timeout=2.5)
    assert captured["timeout"] == 2.5


def test_run_git_raises_typed_timeout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(subprocess, "run", _raise_timeout)
    with pytest.raises(GitCommandTimeout) as exc:
        _run_git(("git", "status"), cwd=tmp_path, timeout=1.0)
    assert exc.value.argv == ("git", "status")
    assert exc.value.timeout == 1.0


def test_run_git_still_raises_failed_on_nonzero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def _fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args[0], 1, stdout="", stderr="bad")

    monkeypatch.setattr(subprocess, "run", _fake_run)
    with pytest.raises(GitCommandFailed) as exc:
        _run_git(("git", "status"), cwd=tmp_path)
    assert exc.value.exit_code == 1
    assert exc.value.stderr == "bad"


def test_branch_exists_raises_timeout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(subprocess, "run", _raise_timeout)
    with pytest.raises(GitCommandTimeout):
        branch_exists(repo_path=tmp_path, branch="main")


def test_timeouts_git_setup_defaults_to_60s() -> None:
    from eden._types import Timeouts

    assert Timeouts().git_setup == 60.0


def test_create_worktree_threads_git_timeout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """create_worktree forwards git_timeout to the carve git calls and stores
    it on the handle so close() reuses it for the teardown remove."""
    import eden.worktree._create as create_mod
    from eden.providers._types import BranchStrategy

    seen: list[float] = []

    def _record_status(*, repo_path: Path, timeout: float = _DEFAULT_GIT_TIMEOUT) -> str:
        seen.append(timeout)
        return ""  # clean tree

    def _record_add(*, timeout: float = _DEFAULT_GIT_TIMEOUT, **_: Any) -> None:
        seen.append(timeout)

    def _record_remove(*, timeout: float = _DEFAULT_GIT_TIMEOUT, **_: Any) -> None:
        seen.append(timeout)

    monkeypatch.setattr(create_mod, "status_porcelain", _record_status)
    monkeypatch.setattr(create_mod, "worktree_add", _record_add)
    monkeypatch.setattr(create_mod, "worktree_remove", _record_remove)

    wt = create_mod.create_worktree(
        host_repo_path=tmp_path,
        strategy=BranchStrategy.merge_to_head(),
        git_timeout=3.5,
    )
    assert wt._git_timeout == 3.5
    wt.close()  # managed worktree -> status_porcelain + worktree_remove
    assert seen == [3.5, 3.5, 3.5]  # add, close-status, remove
