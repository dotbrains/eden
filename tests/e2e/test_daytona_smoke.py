"""Smoke E2E: simulated_agent + daytona provider (fake server) + finalize."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

import eden
from eden.sandboxes import daytona as daytona_sandbox
from tests._fake_daytona import start_fake_daytona

pytestmark = pytest.mark.e2e


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="fake-daytona shell-execs use /bin/sh, not available on Windows",
)
def test_daytona_finalize_writes_sandbox_changes_to_host(
    e2e_git_repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end: a sandbox hook writes a file inside the fake-daytona sandbox;
    finalize() REST-pulls it via copy_file_out and patch_sync.apply lands it
    on the host worktree, and the orchestrator emits `[eden] finalized:`."""
    state_dir = tmp_path / "fake-daytona-state"
    start_fake_daytona(monkeypatch=monkeypatch, state_dir=state_dir)

    # Commands MUST start with `cd /workspace &&` so the file lands in the
    # snapshot-visible directory. The fake server rewrites /workspace to
    # <state_dir>/<id>/workspace; without the cd, cwd defaults to <state_dir>/<id>
    # (outside the snapshot root) and the diff sees no changes.
    sandbox_hook = eden.Hook(
        cmd='cd /workspace && echo "hello-from-cloud" > new_file.txt',
    )
    hooks = eden.Hooks(
        sandbox=eden.SandboxHooks(on_iteration_start=(sandbox_hook,)),
    )

    result = eden.run(
        agent=eden.simulated_agent(output="working\n<promise>COMPLETE</promise>\n"),
        sandbox=daytona_sandbox.provider(),  # api_key from env (set by fake)
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
    assert target_file.read_text(encoding="utf-8").strip() == "hello-from-cloud"

    assert result.log_file_path is not None
    log_body = result.log_file_path.read_text(encoding="utf-8")
    assert "[eden] finalized:" in log_body
    assert "applied=True" in log_body


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="fake-daytona shell-execs use /bin/sh, not available on Windows",
)
def test_daytona_finalize_propagates_deletes(
    e2e_git_repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deleting a file inside the fake-daytona sandbox propagates to the host."""
    assert (e2e_git_repo / "README.md").exists()
    state_dir = tmp_path / "fake-daytona-state"
    start_fake_daytona(monkeypatch=monkeypatch, state_dir=state_dir)

    # Must cd into /workspace first so the rm targets the snapshot root.
    sandbox_hook = eden.Hook(cmd="cd /workspace && rm README.md")
    hooks = eden.Hooks(
        sandbox=eden.SandboxHooks(on_iteration_start=(sandbox_hook,)),
    )

    result = eden.run(
        agent=eden.simulated_agent(output="<promise>COMPLETE</promise>\n"),
        sandbox=daytona_sandbox.provider(),
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
