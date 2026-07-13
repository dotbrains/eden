"""E2E: Worktree APIs own branch lifetime across sandbox calls."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

import eden
from eden.sandboxes.no_sandbox import provider as no_sandbox

pytestmark = pytest.mark.e2e


def test_caller_worktree_hosts_two_sequential_sandboxes(e2e_git_repo: Path) -> None:
    """Split ownership: one worktree, two sandboxes, agents see the same branch."""
    with eden.create_worktree() as wt:
        with eden.create_sandbox(sandbox=no_sandbox(), worktree=wt) as first:
            a = first.run(
                agent=eden.simulated_agent(output="first pass\n<promise>COMPLETE</promise>\n"),
                prompt="x",
                max_iterations=1,
                idle_timeout=10.0,
            )
        # First sandbox is closed; the worktree survives for the second one.
        with eden.create_sandbox(sandbox=no_sandbox(), worktree=wt) as second:
            b = second.run(
                agent=eden.simulated_agent(output="second pass\n<promise>COMPLETE</promise>\n"),
                prompt="y",
                max_iterations=1,
                idle_timeout=10.0,
            )
        assert "first pass" in a.stdout
        assert "second pass" in b.stdout
        assert a.branch == b.branch == wt.branch


def test_worktree_run_executes_agent_in_owned_worktree(e2e_git_repo: Path) -> None:
    """WorktreeHandle.run() is the direct API for AFK work in one worktree."""
    with eden.create_worktree() as wt:
        result = wt.run(
            agent=eden.simulated_agent(output="via worktree\n<promise>COMPLETE</promise>\n"),
            sandbox=no_sandbox(),
            prompt="x",
            max_iterations=1,
            idle_timeout=10.0,
        )
        assert result.branch == wt.branch
        assert "via worktree" in result.stdout


def test_worktree_create_sandbox_returns_split_owner_sandbox(e2e_git_repo: Path) -> None:
    with eden.create_worktree() as wt:
        sandbox = wt.create_sandbox(sandbox=no_sandbox())
        try:
            assert sandbox.worktree is wt
            assert sandbox.owns_worktree is False
            result = sandbox.run(
                agent=eden.simulated_agent(output="method sandbox\n<promise>COMPLETE</promise>\n"),
                prompt="x",
                max_iterations=1,
                idle_timeout=10.0,
            )
        finally:
            close_result = sandbox.close()
        assert result.branch == wt.branch
        assert close_result.action == "released_only"
        assert wt.worktree_path.exists()


def test_create_worktree_accepts_cwd_copy_hooks_and_timeouts(e2e_git_repo: Path) -> None:
    (e2e_git_repo / "seed.txt").write_text("seed\n")
    hooks = eden.Hooks(
        host=eden.HostHooks(
            on_worktree_ready=(
                eden.Hook(f"{sys.executable} -c \"open('hook.txt', 'w').write('ready')\""),
            )
        )
    )

    with eden.create_worktree(
        cwd=e2e_git_repo,
        copy_to_worktree=["seed.txt"],
        hooks=hooks,
        timeouts=eden.Timeouts(hook_step=5.0, git_setup=5.0),
    ) as wt:
        assert (wt.worktree_path / "seed.txt").read_text() == "seed\n"
        assert (wt.worktree_path / "hook.txt").read_text() == "ready"
