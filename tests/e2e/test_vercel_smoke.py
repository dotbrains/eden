"""Smoke E2E: simulated_agent + vercel provider (fake server) + finalize."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

import eden
from eden.sandboxes import vercel as vercel_sandbox
from tests._fake_vercel import start_fake_vercel

pytestmark = pytest.mark.e2e


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="fake-vercel shell-execs use /bin/sh, not available on Windows",
)
def test_vercel_finalize_writes_sandbox_changes_to_host(
    e2e_git_repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end: a sandbox hook writes a file inside the fake-vercel sandbox;
    finalize() REST-pulls it via copy_file_out and patch_sync.apply lands it
    on the host worktree, and the orchestrator emits `[eden] finalized:`."""
    state_dir = tmp_path / "fake-vercel-state"
    start_fake_vercel(monkeypatch=monkeypatch, state_dir=state_dir)

    sandbox_hook = eden.Hook(
        cmd='cd /workspace && echo "hello-from-vercel" > new_file.txt',
    )
    hooks = eden.Hooks(
        sandbox=eden.SandboxHooks(on_iteration_start=(sandbox_hook,)),
    )

    result = eden.run(
        agent=eden.simulated_agent(output="working\n<promise>COMPLETE</promise>\n"),
        sandbox=vercel_sandbox.provider(),  # token from env (set by fake)
        prompt="x",
        max_iterations=1,
        completion_signal="<promise>COMPLETE</promise>",
        idle_timeout=10.0,
        hooks=hooks,
    )

    assert result.completion_signal == "<promise>COMPLETE</promise>"
    target_file = e2e_git_repo / "new_file.txt"
    assert target_file.exists(), (
        f"expected {target_file} to exist after finalize; "
        f"log: {result.log_file_path.read_text() if result.log_file_path else '<no log>'}"
    )
    assert target_file.read_text(encoding="utf-8").strip() == "hello-from-vercel"

    assert result.log_file_path is not None
    log_body = result.log_file_path.read_text(encoding="utf-8")
    assert "[eden] syncing" in log_body
    assert "to host" in log_body


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="fake-vercel shell-execs use /bin/sh, not available on Windows",
)
def test_vercel_finalize_propagates_deletes(
    e2e_git_repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deleting a file inside the fake-vercel sandbox propagates to the host."""
    assert (e2e_git_repo / "README.md").exists()
    state_dir = tmp_path / "fake-vercel-state"
    start_fake_vercel(monkeypatch=monkeypatch, state_dir=state_dir)

    sandbox_hook = eden.Hook(cmd="cd /workspace && rm README.md")
    hooks = eden.Hooks(
        sandbox=eden.SandboxHooks(on_iteration_start=(sandbox_hook,)),
    )

    result = eden.run(
        agent=eden.simulated_agent(output="<promise>COMPLETE</promise>\n"),
        sandbox=vercel_sandbox.provider(),
        prompt="x",
        max_iterations=1,
        completion_signal="<promise>COMPLETE</promise>",
        idle_timeout=10.0,
        hooks=hooks,
    )

    assert result.completion_signal == "<promise>COMPLETE</promise>"
    assert not (e2e_git_repo / "README.md").exists()
    assert result.log_file_path is not None
    assert "[eden] syncing" in result.log_file_path.read_text(encoding="utf-8")
