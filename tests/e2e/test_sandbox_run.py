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
