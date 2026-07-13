"""Unit tests for the post-run commit census helpers.

``head_sha`` snapshots the branch tip before the agent runs; ``new_commits``
lists what the agent committed since (``git rev-list base..HEAD``). Both are
best-effort: bad refs / unreadable HEAD yield empty results, never raise.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from eden.worktree._git import head_sha, new_commits

pytestmark = pytest.mark.unit


def _commit(repo: Path, name: str) -> str:
    (repo / name).write_text(f"{name}\n")
    subprocess.run(["git", "add", name], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "--no-gpg-sign", "-m", name],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    out = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    )
    return out.stdout.strip()


def test_head_sha_returns_current_tip(tmp_git_repo: Path) -> None:
    sha = head_sha(repo_path=tmp_git_repo)
    assert len(sha) == 40
    assert all(c in "0123456789abcdef" for c in sha)


def test_new_commits_lists_agent_commits_newest_first(tmp_git_repo: Path) -> None:
    base = head_sha(repo_path=tmp_git_repo)
    first = _commit(tmp_git_repo, "a.txt")
    second = _commit(tmp_git_repo, "b.txt")

    shas = new_commits(worktree_path=tmp_git_repo, base_sha=base)

    assert shas == (second, first)


def test_new_commits_empty_when_no_commits_since_base(tmp_git_repo: Path) -> None:
    base = head_sha(repo_path=tmp_git_repo)
    assert new_commits(worktree_path=tmp_git_repo, base_sha=base) == ()


def test_new_commits_empty_base_disables_census(tmp_git_repo: Path) -> None:
    _commit(tmp_git_repo, "a.txt")
    assert new_commits(worktree_path=tmp_git_repo, base_sha="") == ()


def test_new_commits_invalid_base_is_best_effort(tmp_git_repo: Path) -> None:
    # A garbage ref makes ``git rev-list`` exit non-zero; the census must
    # swallow it rather than sink the run.
    assert new_commits(worktree_path=tmp_git_repo, base_sha="deadbeef" * 5) == ()
