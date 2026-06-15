"""E2E: ``RunResult.commits`` reflects commits the agent made on the branch.

Drives ``eden.run()`` with a ``cli_agent`` whose subprocess commits a file in
the worktree (the no-sandbox provider runs the agent in the worktree, so its
commits land on the run's branch) and then prints the completion signal. The
post-run census must surface that commit on ``RunResult.commits``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

import eden
from eden.agents._context import IterationContext
from eden.agents.cli import cli_agent
from eden.sandboxes.no_sandbox import provider as no_sandbox

pytestmark = pytest.mark.e2e


def _committing_agent_argv() -> list[str]:
    """argv for a python agent that commits one file, then signals done."""
    script = (
        "import subprocess, sys\n"
        "open('agent_made_this.txt', 'w').write('hi\\n')\n"
        "subprocess.run(['git', 'add', '-A'], check=True)\n"
        "subprocess.run(\n"
        "    ['git', 'commit', '--no-gpg-sign', '-m', 'eden: agent change'],\n"
        "    check=True,\n"
        ")\n"
        "sys.stdout.write('<promise>COMPLETE</promise>\\n')\n"
        "sys.stdout.flush()\n"
    )
    return [sys.executable, "-c", script]


def test_run_result_collects_agent_commit(e2e_git_repo: Path) -> None:
    def _build(ctx: IterationContext) -> list[str]:
        return _committing_agent_argv()

    agent = cli_agent(name="committer", model="x", binary="ignored", build_argv=_build)

    result = eden.run(
        agent=agent,
        sandbox=no_sandbox(),
        prompt="x",
        max_iterations=1,
        completion_signal="<promise>COMPLETE</promise>",
        idle_timeout=30.0,
    )

    assert len(result.commits) == 1
    assert len(result.commits[0].sha) == 40


def test_run_result_no_commits_when_agent_makes_none(e2e_git_repo: Path) -> None:
    def _build(ctx: IterationContext) -> list[str]:
        return [
            sys.executable,
            "-c",
            "import sys; sys.stdout.write('<promise>COMPLETE</promise>\\n')",
        ]

    agent = cli_agent(name="noop", model="x", binary="ignored", build_argv=_build)

    result = eden.run(
        agent=agent,
        sandbox=no_sandbox(),
        prompt="x",
        max_iterations=1,
        completion_signal="<promise>COMPLETE</promise>",
        idle_timeout=30.0,
    )

    assert result.commits == []
