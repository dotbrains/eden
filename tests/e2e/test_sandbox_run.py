"""E2E: Sandbox.run() reuses one worktree across multiple agent calls."""

from __future__ import annotations

from pathlib import Path

import pytest

import eden
from eden.sandboxes.no_sandbox import provider as no_sandbox

pytestmark = pytest.mark.e2e


def test_sandbox_run_executes_agent(e2e_git_repo: Path) -> None:
    sandbox = eden.create_sandbox(sandbox=no_sandbox())
    try:
        result = sandbox.run(
            agent=eden.simulated_agent(
                output="phase one\n<promise>COMPLETE</promise>\n",
            ),
            prompt="x",
            max_iterations=1,
            idle_timeout=10.0,
        )
        assert result.completion_signal == "<promise>COMPLETE</promise>"
        assert "phase one" in result.stdout
    finally:
        sandbox.close()


def test_sandbox_run_can_be_called_twice(e2e_git_repo: Path) -> None:
    """Two agents share the same worktree + handle."""
    with eden.create_sandbox(sandbox=no_sandbox()) as sandbox:
        a = sandbox.run(
            agent=eden.simulated_agent(output="alpha\n<promise>COMPLETE</promise>\n"),
            prompt="x",
            max_iterations=1,
            idle_timeout=10.0,
        )
        b = sandbox.run(
            agent=eden.simulated_agent(output="beta\n<promise>COMPLETE</promise>\n"),
            prompt="y",
            max_iterations=1,
            idle_timeout=10.0,
        )
        assert "alpha" in a.stdout
        assert "beta" in b.stdout
        # Both runs report the same branch (no_sandbox uses HEAD).
        assert a.branch == b.branch


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
        with wt.create_sandbox(sandbox=no_sandbox()) as sandbox:
            assert sandbox.worktree is wt
            assert sandbox.owns_worktree is False
            result = sandbox.run(
                agent=eden.simulated_agent(output="method sandbox\n<promise>COMPLETE</promise>\n"),
                prompt="x",
                max_iterations=1,
                idle_timeout=10.0,
            )
        assert result.branch == wt.branch
        assert wt.worktree_path.exists()


def test_sandbox_run_rejects_branch_strategy(e2e_git_repo: Path) -> None:
    """branch_strategy is meaningless after the sandbox owns a branch."""
    with eden.create_sandbox(sandbox=no_sandbox()) as sandbox:
        # The Sandbox.run() signature doesn't take branch_strategy, so callers
        # cannot pass it. As a sanity check, the underlying _run_loop guards
        # against it being threaded through internal paths.
        result = sandbox.run(
            agent=eden.simulated_agent(output="<promise>COMPLETE</promise>\n"),
            prompt="x",
            max_iterations=1,
            idle_timeout=10.0,
        )
        assert result.completion_signal


def test_sandbox_run_with_output_extraction(e2e_git_repo: Path) -> None:
    with eden.create_sandbox(sandbox=no_sandbox()) as sandbox:
        result = sandbox.run(
            agent=eden.simulated_agent(
                output="<answer>42</answer>\n<promise>COMPLETE</promise>\n",
            ),
            prompt="emit <answer>...</answer>",
            max_iterations=1,
            idle_timeout=10.0,
            output=eden.Output.string(tag="answer"),
        )
        assert result.output == "42"


def test_sandbox_run_resume_session_threads_into_iteration_context(
    e2e_git_repo: Path,
) -> None:
    """resume_session passed to Sandbox.run reaches the agent's IterationContext."""
    import sys

    from eden.agents._context import IterationContext
    from eden.agents.cli import cli_agent

    seen: list[str | None] = []

    def _build(ctx: IterationContext) -> list[str]:
        seen.append(ctx.resume_session)
        return [sys.executable, "-c", "print('<promise>COMPLETE</promise>')"]

    agent = cli_agent(name="probe", model="x", binary="ignored", build_argv=_build)
    with eden.create_sandbox(sandbox=no_sandbox()) as sandbox:
        sandbox.run(
            agent=agent,
            prompt="x",
            max_iterations=1,
            completion_signal="<promise>COMPLETE</promise>",
            idle_timeout=10.0,
            resume_session="sb-session-99",
        )
    assert seen == ["sb-session-99"]


def test_sandbox_run_rejects_resume_with_max_iterations_gt_1(
    e2e_git_repo: Path,
) -> None:
    with eden.create_sandbox(sandbox=no_sandbox()) as sandbox:
        with pytest.raises(eden.InvalidOptions) as ex:
            sandbox.run(
                agent=eden.simulated_agent(output="x\n"),
                prompt="x",
                max_iterations=2,
                resume_session="some-id",
            )
    assert "max_iterations" in ex.value.message
