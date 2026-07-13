"""End-to-end smoke tests: drive ``eden.run`` through the test providers.

These confirm the test providers are full ``SandboxProvider``
implementations and not just stubs — the orchestrator can create
sandboxes through them, execute the simulated agent, capture commits,
and (for isolated) finalize state.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from eden import run, simulated_agent
from eden.sandboxes.test_bind_mount import (
    CallLog,
)
from eden.sandboxes.test_bind_mount import (
    provider as bind_mount_provider,
)
from eden.sandboxes.test_isolated import provider as isolated_provider

pytestmark = pytest.mark.unit


def test_bind_mount_drives_a_simulated_run(tmp_git_repo: Path) -> None:
    log = CallLog()
    result = run(
        cwd=tmp_git_repo,
        sandbox=bind_mount_provider(call_log=log),
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
    result = run(
        cwd=tmp_git_repo,
        sandbox=isolated_provider(),
        agent=simulated_agent(
            output="hello\n<promise>COMPLETE</promise>\n",
        ),
        prompt="ignored",
        max_iterations=1,
    )
    assert len(result.iterations) == 1
    assert result.completion_signal == "<promise>COMPLETE</promise>"
