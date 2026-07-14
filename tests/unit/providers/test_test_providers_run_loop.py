"""End-to-end smoke tests: drive ``eden.run`` through the test providers.

These confirm the test providers are full ``SandboxProvider``
implementations and not just stubs — the orchestrator can create
sandboxes through them, execute the simulated agent, capture commits,
and (for isolated) finalize state.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from eden.agents import simulated_agent
from eden.orchestrator import run as eden_run
from eden.sandboxes import test_bind_mount, test_isolated
from eden.sandboxes.test_bind_mount import (
    CallLog,
)

pytestmark = pytest.mark.unit


def test_bind_mount_drives_a_simulated_run(tmp_git_repo: Path) -> None:
    log = CallLog()
    result = eden_run(
        cwd=tmp_git_repo,
        sandbox=test_bind_mount.provider(call_log=log),
        agent=simulated_agent(
            output="hello\n<promise>COMPLETE</promise>\n",
        ),
        prompt="ignored",
        max_iterations=1,
    )
    assert len(result.iterations) == 1
    assert result.completion_signal == "<promise>COMPLETE</promise>"
    # Sandbox was closed via `close()` — log should reflect that.
    assert log.closed is True


def test_isolated_drives_a_simulated_run(tmp_git_repo: Path) -> None:
    result = eden_run(
        cwd=tmp_git_repo,
        sandbox=test_isolated.provider(),
        agent=simulated_agent(
            output="hello\n<promise>COMPLETE</promise>\n",
        ),
        prompt="ignored",
        max_iterations=1,
    )
    assert len(result.iterations) == 1
    assert result.completion_signal == "<promise>COMPLETE</promise>"
