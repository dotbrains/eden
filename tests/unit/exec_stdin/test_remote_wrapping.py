"""Tests that remote/container exec implementations preserve ``stdin=``."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from eden.providers._types import ExecResult

pytestmark = pytest.mark.unit


def test_daytona_wraps_stdin_via_base64_pipe() -> None:
    """Confirm daytona's exec() wraps the cmd to inject stdin through the REST shell."""
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
    assert "base64 -d" in sent_cmd
    assert "(cat -)" in sent_cmd


def test_vercel_wraps_stdin_via_base64_pipe() -> None:
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
    from eden.providers._impl.container_handle import ContainerHandle

    handle = ContainerHandle(
        binary="docker",
        container_id="abc123",
        worktree_path=Path("/workspace"),
        host_worktree_path=Path("/host"),
    )
    with patch("eden.providers._impl.container_handle.stream_exec") as mock_stream_exec:
        mock_stream_exec.return_value = ExecResult(stdout="", stderr="", exit_code=0)
        handle.exec("cat -", stdin="piped")

    assert mock_stream_exec.call_count == 1
    call = mock_stream_exec.call_args
    assert call.kwargs["stdin"] == "piped"
    argv = call.args[0]
    assert argv[0] == "docker"
    assert argv[1] == "exec"
    assert "-i" in argv
