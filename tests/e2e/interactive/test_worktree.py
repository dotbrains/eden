"""E2E: interactive branch and worktree behavior."""

from __future__ import annotations

from pathlib import Path

import pytest

import eden
from eden.sandboxes.no_sandbox import provider as no_sandbox
from tests.e2e.interactive_helpers import exit_zero_agent

pytestmark = pytest.mark.e2e


def test_interactive_carves_named_branch(e2e_git_repo: Path) -> None:
    result = eden.interactive(
        agent=exit_zero_agent(),
        sandbox=no_sandbox(),
        branch_strategy=eden.BranchStrategy.named("eden/interactive-test"),
    )
    assert result.branch == "eden/interactive-test"
    assert result.worktree_path != e2e_git_repo


def test_worktree_interactive_uses_existing_worktree(e2e_git_repo: Path) -> None:
    with eden.create_worktree() as wt:
        result = wt.interactive(agent=exit_zero_agent(), sandbox=no_sandbox())
        assert result.exit_code == 0
        assert result.branch == wt.branch
        assert result.worktree_path == wt.worktree_path
        assert wt.worktree_path.exists()
