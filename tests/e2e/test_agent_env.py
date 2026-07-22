"""E2E: per-agent environment additions reach the subprocess."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

import eden
from eden.sandboxes.no_sandbox import provider as no_sandbox

pytestmark = pytest.mark.e2e


def _env_agent(key: str) -> eden.Agent:
    script = (
        "import os, sys\n"
        f"sys.stdout.write(os.environ.get({key!r}, '<missing>') + '\\n')\n"
        "sys.stdout.write('<promise>COMPLETE</promise>\\n')\n"
    )
    return eden.cli_agent(
        name="env-agent",
        model="test",
        binary=sys.executable,
        extra_args=("-c", script),
        env={key: "from-agent"},
    )


def test_run_passes_agent_env_to_subprocess(e2e_git_repo: Path) -> None:
    key = "EDEN_AGENT_ENV_TEST"
    os.environ.pop(key, None)

    result = eden.run(
        agent=_env_agent(key),
        sandbox=no_sandbox(),
        prompt="ignored",
        max_iterations=1,
        idle_timeout=10.0,
    )

    assert "from-agent" in result.stdout


def test_sandbox_run_passes_agent_env_to_subprocess(e2e_git_repo: Path) -> None:
    key = "EDEN_SANDBOX_AGENT_ENV_TEST"
    os.environ.pop(key, None)
    sandbox = eden.create_sandbox(sandbox=no_sandbox())
    try:
        result = sandbox.run(
            agent=_env_agent(key),
            prompt="ignored",
            max_iterations=1,
            idle_timeout=10.0,
        )
    finally:
        sandbox.close()

    assert "from-agent" in result.stdout
