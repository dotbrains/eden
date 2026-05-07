"""E2E: resume_session option validation and threading into IterationContext."""

from __future__ import annotations

from pathlib import Path

import pytest

import eden
from eden.agents._context import IterationContext
from eden.agents.cli import cli_agent
from eden.sandboxes.no_sandbox import provider as no_sandbox

pytestmark = pytest.mark.e2e


def test_resume_session_with_max_iterations_gt_1_rejected(e2e_git_repo: Path) -> None:
    with pytest.raises(eden.InvalidOptions) as ex:
        eden.run(
            agent=eden.simulated_agent(output="x\n"),
            sandbox=no_sandbox(),
            prompt="x",
            max_iterations=2,
            resume_session="some-id",
        )
    assert "max_iterations" in ex.value.message


def test_resume_session_threads_into_iteration_context(e2e_git_repo: Path) -> None:
    """A custom build_argv sees ctx.resume_session — proves orchestrator plumbing."""
    seen: list[str | None] = []

    def _build(ctx: IterationContext) -> list[str]:
        seen.append(ctx.resume_session)
        # Run the simulated_agent's underlying script via cli_agent shim.
        import sys as _sys

        return [_sys.executable, "-c", "print('<promise>COMPLETE</promise>')"]

    agent = cli_agent(name="probe", model="x", binary="ignored", build_argv=_build)
    eden.run(
        agent=agent,
        sandbox=no_sandbox(),
        prompt="x",
        max_iterations=1,
        completion_signal="<promise>COMPLETE</promise>",
        idle_timeout=10.0,
        resume_session="my-session-42",
    )
    assert seen == ["my-session-42"]


def test_no_resume_session_threads_none(e2e_git_repo: Path) -> None:
    seen: list[str | None] = []

    def _build(ctx: IterationContext) -> list[str]:
        seen.append(ctx.resume_session)
        import sys as _sys

        return [_sys.executable, "-c", "print('<promise>COMPLETE</promise>')"]

    agent = cli_agent(name="probe", model="x", binary="ignored", build_argv=_build)
    eden.run(
        agent=agent,
        sandbox=no_sandbox(),
        prompt="x",
        max_iterations=1,
        completion_signal="<promise>COMPLETE</promise>",
        idle_timeout=10.0,
    )
    assert seen == [None]
