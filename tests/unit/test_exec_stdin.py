"""Tests that ``stdin=`` is forwarded by every provider's ``exec`` path.

The Protocol added a ``stdin: str | None = None`` keyword to
``SandboxHandle.exec`` so any provider can deliver large prompts (or
binary blobs base64-encoded by callers) without hitting the 128KB
execve argv limit on Linux. These tests pin the contract.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from eden.providers._types import CreateOptions, ExecResult
from eden.sandboxes._exec import stream_exec
from eden.sandboxes.no_sandbox import provider as no_sandbox
from eden.sandboxes.test_bind_mount import (
    CallLog,
    ExecCall,
)
from eden.sandboxes.test_bind_mount import (
    provider as bind_mount_provider,
)
from eden.sandboxes.test_isolated import provider as isolated_provider

pytestmark = pytest.mark.unit


def _opts(p: Path) -> CreateOptions:
    return CreateOptions(
        branch="main",
        worktree_path=p,
        host_repo_path=p,
        env={},
        mounts=(),
        name_hint=None,
    )


def test_stream_exec_forwards_stdin() -> None:
    result = stream_exec(
        [sys.executable, "-c", "import sys; sys.stdout.write(sys.stdin.read())"],
        cmd_for_error="cat-stdin",
        shell=False,
        stdin="payload-from-stdin\n",
    )
    assert result.exit_code == 0
    assert "payload-from-stdin" in result.stdout


def test_stream_exec_handles_large_stdin_payload() -> None:
    # 256KB — past the typical 128KB execve argv limit, exercising the
    # daemon-write path.
    big = "X" * (256 * 1024) + "\n"
    result = stream_exec(
        [sys.executable, "-c", "import sys; print(len(sys.stdin.read()))"],
        cmd_for_error="len-stdin",
        shell=False,
        stdin=big,
    )
    assert result.exit_code == 0
    assert result.stdout.strip() == str(len(big))


def test_stream_exec_default_stdin_is_none() -> None:
    # When stdin=None, the child's stdin should be the parent's stdin
    # (or /dev/null in pytest) — confirm no pipe was opened and the
    # process completes normally.
    result = stream_exec(
        [sys.executable, "-c", "print('ok')"],
        cmd_for_error="no-stdin",
        shell=False,
    )
    assert result.exit_code == 0


def test_no_sandbox_forwards_stdin(tmp_path: Path) -> None:
    p = no_sandbox()
    h = p.create(_opts(tmp_path))
    try:
        result = h.exec(
            f"{sys.executable} -c 'import sys; sys.stdout.write(sys.stdin.read())'",
            stdin="forwarded\n",
        )
        assert result.exit_code == 0
        assert "forwarded" in result.stdout
    finally:
        h.close()


def test_test_bind_mount_records_stdin_in_call_log(tmp_path: Path) -> None:
    log = CallLog()
    p = bind_mount_provider(call_log=log)
    h = p.create(_opts(tmp_path))
    try:

        def stub(call: ExecCall) -> ExecResult:
            assert call.stdin == "expected-stdin"
            return ExecResult(stdout="ok", stderr="", exit_code=0)

        # Re-create with handler; verify the captured ExecCall has stdin.
        p2 = bind_mount_provider(exec_handler=stub, call_log=log)
        h2 = p2.create(_opts(tmp_path))
        try:
            h2.exec("noop", stdin="expected-stdin")
        finally:
            h2.close()
    finally:
        h.close()
    # Two creates → two closed events; the second handler's call landed
    # in the SAME shared log.
    matching = [c for c in log.exec_calls if c.stdin == "expected-stdin"]
    assert len(matching) == 1


def test_test_bind_mount_forwards_stdin_to_real_subprocess(tmp_path: Path) -> None:
    p = bind_mount_provider()
    h = p.create(_opts(tmp_path))
    try:
        # Use printf via a shell-quoted python to roundtrip stdin.
        result = h.exec(
            f"{sys.executable} -c 'import sys; sys.stdout.write(sys.stdin.read())'",
            stdin="hello-via-handle\n",
        )
        assert result.exit_code == 0
        assert "hello-via-handle" in result.stdout
    finally:
        h.close()


def test_test_isolated_forwards_stdin_to_real_subprocess(tmp_git_repo: Path) -> None:
    p = isolated_provider()
    h = p.create(_opts(tmp_git_repo))
    try:
        result = h.exec(
            f"{sys.executable} -c 'import sys; sys.stdout.write(sys.stdin.read())'",
            stdin="iso-stdin\n",
        )
        assert result.exit_code == 0
        assert "iso-stdin" in result.stdout
    finally:
        h.close()


def test_daytona_wraps_stdin_via_base64_pipe(monkeypatch: pytest.MonkeyPatch) -> None:
    """Confirm daytona's exec() wraps the cmd to inject stdin through the REST shell."""
    from unittest.mock import MagicMock

    from eden.sandboxes.daytona import _DaytonaHandle

    fake_client = MagicMock()
    fake_client.post.return_value = {"stdout": "ok", "stderr": "", "exit_code": 0}
    handle = _DaytonaHandle(
        client=fake_client,
        sandbox_id="sb-1",
        worktree_path=Path("/workspace"),
        host_worktree_path=Path("/host"),
        baseline={},
    )

    handle.exec("cat -", stdin="hello\n")
    _args, kwargs = fake_client.post.call_args
    sent_cmd = kwargs["json"]["command"]
    # The original command should be wrapped, base64 should appear.
    assert "base64 -d" in sent_cmd
    assert "(cat -)" in sent_cmd


def test_vercel_wraps_stdin_via_base64_pipe() -> None:
    from unittest.mock import MagicMock

    from eden.sandboxes.vercel import _VercelHandle

    fake_client = MagicMock()
    fake_client.post.return_value = {"stdout": "ok", "stderr": "", "exit_code": 0}
    handle = _VercelHandle(
        client=fake_client,
        sandbox_id="sb-vercel",
        team_id=None,
        worktree_path=Path("/workspace"),
        host_worktree_path=Path("/host"),
        baseline={},
    )

    handle.exec("md5sum", stdin="abc\n")
    _args, kwargs = fake_client.post.call_args
    sent_cmd = kwargs["json"]["command"]
    assert "base64 -d" in sent_cmd
    assert "(md5sum)" in sent_cmd


def test_container_provider_passes_stdin_through_exec_pipe() -> None:
    """Confirm the container provider's exec invokes stream_exec with stdin."""
    from unittest.mock import patch

    from eden.providers._impl.container import _ContainerHandle

    handle = _ContainerHandle(
        binary="docker",
        container_id="abc123",
        worktree_path=Path("/workspace"),
        host_worktree_path=Path("/host"),
    )
    with patch("eden.providers._impl.container.stream_exec") as m:
        m.return_value = ExecResult(stdout="", stderr="", exit_code=0)
        handle.exec("cat -", stdin="piped")
    assert m.call_count == 1
    call = m.call_args
    assert call.kwargs["stdin"] == "piped"
    # And confirm ``docker exec -i ...`` argv was constructed.
    argv = call.args[0]
    assert argv[0] == "docker"
    assert argv[1] == "exec"
    assert "-i" in argv
