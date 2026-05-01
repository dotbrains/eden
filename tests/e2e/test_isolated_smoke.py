"""Smoke E2E: simulated_agent + isolated provider + finalize patch-sync."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

import eden
from eden.sandboxes import isolated as isolated_sandbox

pytestmark = pytest.mark.e2e


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="sandbox hook uses /bin/sh, not available on Windows",
)
def test_isolated_finalize_writes_sandbox_changes_to_host(e2e_git_repo: Path) -> None:
    """End-to-end: a sandbox hook writes a file inside the isolated root;
    after the iteration completes, finalize() copies that file to the host
    worktree, and the orchestrator emits a `[eden] finalized:` message."""
    sandbox_hook = eden.Hook(
        cmd='echo "hello-from-agent" > new_file.txt',
    )
    hooks = eden.Hooks(
        sandbox=eden.SandboxHooks(on_iteration_start=(sandbox_hook,)),
    )

    result = eden.run(
        agent=eden.simulated_agent(output="working\n<promise>COMPLETE</promise>\n"),
        sandbox=isolated_sandbox.provider(),
        prompt="x",
        max_iterations=1,
        completion_signal="<promise>COMPLETE</promise>",
        idle_timeout=10.0,
        hooks=hooks,
    )

    assert result.completion_signal == "<promise>COMPLETE</promise>"
    target_file = e2e_git_repo / "new_file.txt"
    assert target_file.exists()
    assert target_file.read_text(encoding="utf-8").strip() == "hello-from-agent"

    assert result.log_file_path is not None
    log_body = result.log_file_path.read_text(encoding="utf-8")
    assert "[eden] finalized:" in log_body
    assert "applied=True" in log_body


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="sandbox hook uses /bin/sh, not available on Windows",
)
def test_isolated_finalize_propagates_deletes(e2e_git_repo: Path) -> None:
    """Deleting a file inside the isolated sandbox propagates to the host."""
    assert (e2e_git_repo / "README.md").exists()
    sandbox_hook = eden.Hook(cmd="rm README.md")
    hooks = eden.Hooks(
        sandbox=eden.SandboxHooks(on_iteration_start=(sandbox_hook,)),
    )

    result = eden.run(
        agent=eden.simulated_agent(output="<promise>COMPLETE</promise>\n"),
        sandbox=isolated_sandbox.provider(),
        prompt="x",
        max_iterations=1,
        completion_signal="<promise>COMPLETE</promise>",
        idle_timeout=10.0,
        hooks=hooks,
    )

    assert result.completion_signal == "<promise>COMPLETE</promise>"
    assert not (e2e_git_repo / "README.md").exists()
    assert result.log_file_path is not None
    assert "applied=True" in result.log_file_path.read_text(encoding="utf-8")
