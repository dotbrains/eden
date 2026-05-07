"""E2E: ``eden.aio`` async wrappers run agents on the asyncio executor."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

import eden
from eden import aio
from eden.sandboxes.no_sandbox import provider as no_sandbox

pytestmark = pytest.mark.e2e


def _run_async(coro):  # type: ignore[no-untyped-def]
    """Execute a coroutine and return its result. Mirrors asyncio.run but
    works in environments that already have a loop policy set up."""
    return asyncio.run(coro)


def test_aio_run_returns_run_result(e2e_git_repo: Path) -> None:
    async def go() -> eden.RunResult:
        return await aio.run(
            agent=eden.simulated_agent(
                output="hello\n<promise>COMPLETE</promise>\n",
            ),
            sandbox=no_sandbox(),
            prompt="x",
            max_iterations=1,
            idle_timeout=10.0,
        )

    result = _run_async(go())
    assert isinstance(result, eden.RunResult)
    assert result.completion_signal == "<promise>COMPLETE</promise>"
    assert "hello" in result.stdout


def test_aio_run_propagates_invalid_options(e2e_git_repo: Path) -> None:
    """Validation errors raised by the sync core surface through the wrapper."""

    async def go() -> None:
        await aio.run(
            agent=eden.simulated_agent(output="x\n"),
            sandbox=no_sandbox(),
            prompt="x",
            max_iterations=2,
            output=eden.Output.string(tag="answer"),  # rejected with maxIter>1
        )

    with pytest.raises(eden.InvalidOptions):
        _run_async(go())


def test_aio_create_sandbox_returns_sandbox(e2e_git_repo: Path) -> None:
    async def go() -> str:
        s = await aio.create_sandbox(sandbox=no_sandbox())
        try:
            assert isinstance(s, eden.Sandbox)
            # Mix sync .run() inside async code via the documented to_thread recipe.
            result = await asyncio.to_thread(
                s.run,
                agent=eden.simulated_agent(
                    output="phase\n<promise>COMPLETE</promise>\n",
                ),
                prompt="x",
                max_iterations=1,
                idle_timeout=10.0,
            )
            return result.stdout
        finally:
            s.close()

    out = _run_async(go())
    assert "phase" in out


def test_aio_run_composes_with_gather(e2e_git_repo: Path) -> None:
    """Two aio.run calls execute concurrently via the default thread executor."""

    async def go() -> tuple[str, str]:
        a, b = await asyncio.gather(
            aio.run(
                agent=eden.simulated_agent(output="alpha\n<promise>COMPLETE</promise>\n"),
                sandbox=no_sandbox(),
                prompt="x",
                max_iterations=1,
                idle_timeout=10.0,
                # Distinct branch names so the worktree-locks don't collide on HEAD.
                branch_strategy=eden.BranchStrategy.named("eden/aio-a"),
            ),
            aio.run(
                agent=eden.simulated_agent(output="beta\n<promise>COMPLETE</promise>\n"),
                sandbox=no_sandbox(),
                prompt="y",
                max_iterations=1,
                idle_timeout=10.0,
                branch_strategy=eden.BranchStrategy.named("eden/aio-b"),
            ),
        )
        return a.stdout, b.stdout

    a, b = _run_async(go())
    assert "alpha" in a
    assert "beta" in b


def test_aio_interactive_returns_interactive_result(e2e_git_repo: Path) -> None:
    """Interactive over the async wrapper returns the same result type."""
    import sys

    from eden.agents._context import IterationContext
    from eden.agents.cli import cli_agent

    def _build(_ctx: IterationContext) -> list[str]:
        return [sys.executable, "-c", "import sys; sys.exit(0)"]

    agent = cli_agent(name="probe", model="x", binary="ignored", build_argv=_build)

    async def go() -> eden.InteractiveResult:
        return await aio.interactive(agent=agent, sandbox=no_sandbox())

    result = _run_async(go())
    assert isinstance(result, eden.InteractiveResult)
    assert result.exit_code == 0
