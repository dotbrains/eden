"""Verify host-side git invocations run under a pinned C locale.

Eden's worktree management uses ``--porcelain`` output and exit codes,
both of which are locale-independent, so the immediate motivation is
defensive: a future caller that substring-matches git's stderr would
silently break under non-English locales without ``LC_ALL=C``. This
test pins the contract.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from eden.worktree._git import _run_git, branch_exists, c_locale_env, worktree_add

pytestmark = pytest.mark.unit


def test_c_locale_env_pins_required_keys() -> None:
    env = c_locale_env()
    assert env["LC_ALL"] == "C"
    assert env["LANG"] == "C"
    # LANGUAGE wins over LC_ALL for git message selection, so it must be
    # cleared rather than left to inherit a user setting.
    assert env["LANGUAGE"] == ""


def test_c_locale_env_inherits_unrelated_os_environ() -> None:
    """Non-locale env vars from the parent process pass through."""
    with patch.dict(os.environ, {"EDEN_TEST_PASSTHROUGH": "yes"}, clear=False):
        env = c_locale_env()
        assert env.get("EDEN_TEST_PASSTHROUGH") == "yes"


def test_c_locale_env_overrides_inherited_locale() -> None:
    """A caller running under a French locale still hands git ``C``."""
    with patch.dict(
        os.environ,
        {"LC_ALL": "fr_FR.UTF-8", "LANG": "fr_FR.UTF-8", "LANGUAGE": "fr_FR"},
        clear=False,
    ):
        env = c_locale_env()
        assert env["LC_ALL"] == "C"
        assert env["LANG"] == "C"
        assert env["LANGUAGE"] == ""


def test_run_git_passes_c_locale_env(tmp_path: Path) -> None:
    """``_run_git`` forwards the pinned locale to ``subprocess.run``."""
    seen: dict[str, Any] = {}
    fake = subprocess.CompletedProcess(args=(), returncode=0, stdout="", stderr="")

    def _capture(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        seen.update(kwargs)
        return fake

    with patch("eden.worktree._git.subprocess.run", side_effect=_capture):
        _run_git(("git", "status", "--porcelain"), cwd=tmp_path)

    assert seen["env"]["LC_ALL"] == "C"
    assert seen["env"]["LANG"] == "C"
    assert seen["env"]["LANGUAGE"] == ""


def test_branch_exists_passes_c_locale_env(tmp_path: Path) -> None:
    """``branch_exists`` uses subprocess.run directly — pin must apply there too."""
    seen: dict[str, Any] = {}
    fake = subprocess.CompletedProcess(args=(), returncode=0, stdout="", stderr="")

    def _capture(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        seen.update(kwargs)
        return fake

    with patch("eden.worktree._git.subprocess.run", side_effect=_capture):
        branch_exists(repo_path=tmp_path, branch="main")

    assert seen["env"]["LC_ALL"] == "C"
    assert seen["env"]["LANG"] == "C"


def test_worktree_add_disables_branch_auto_setup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Generated worktrees must not contend on .git/config tracking writes."""
    seen: list[tuple[str, ...]] = []

    monkeypatch.setattr("eden.worktree._git._check_collisions", lambda **_: None)

    def _capture(argv: tuple[str, ...], *, cwd: Path, timeout: float = 60.0) -> tuple[str, str]:
        seen.append(argv)
        return "", ""

    monkeypatch.setattr("eden.worktree._git._run_git", _capture)

    worktree_add(
        repo_path=tmp_path,
        worktree_path=tmp_path / "wt",
        branch="eden/x",
        base="HEAD",
    )

    argv = seen[0]
    assert argv[:6] == (
        "git",
        "-c",
        "branch.autoSetupMerge=false",
        "-c",
        "push.autoSetupRemote=false",
        "worktree",
    )
