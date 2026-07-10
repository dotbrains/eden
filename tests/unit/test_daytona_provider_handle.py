"""Verify _DaytonaHandle exec, copy, and close behavior."""

from __future__ import annotations

import base64
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from eden.providers._impl.http_rest import RestClient
from eden.providers._types import ExecResult
from eden.sandboxes.errors import ExecFailed
from tests.unit.daytona_provider_helpers import mock_client

pytestmark = pytest.mark.unit


def test_handle_exec_returns_exec_result() -> None:
    from eden.sandboxes.daytona import _DaytonaHandle

    client = mock_client(
        {"stdout": "hello\n", "stderr": "", "exit_code": 0},
    )
    handle = _DaytonaHandle(
        client=client,
        sandbox_id="sb-1",
        worktree_path=Path("/workspace"),
        host_worktree_path=Path("/host"),
        baseline={},
    )
    result = handle.exec("echo hello")
    assert isinstance(result, ExecResult)
    assert result.stdout == "hello\n"
    assert result.exit_code == 0
    client.post.assert_called_once()
    args, kwargs = client.post.call_args
    assert args[0] == "/toolbox/sb-1/process/execute"
    assert kwargs["json"]["command"] == "echo hello"


def test_handle_exec_returns_neg_one_on_rest_failure() -> None:
    from eden.sandboxes.daytona import _DaytonaHandle

    client = MagicMock(spec=RestClient)
    client.post.side_effect = RuntimeError("network down")
    handle = _DaytonaHandle(
        client=client,
        sandbox_id="sb-1",
        worktree_path=Path("/workspace"),
        host_worktree_path=Path("/host"),
        baseline={},
    )
    result = handle.exec("anything")
    assert result.exit_code == -1
    assert "network down" in result.stderr


def test_handle_copy_file_in_base64_shells(tmp_path: Path) -> None:
    from eden.sandboxes.daytona import _DaytonaHandle

    src = tmp_path / "payload.bin"
    src.write_bytes(b"\x00\x01\x02\x03")
    client = mock_client({"stdout": "", "stderr": "", "exit_code": 0})
    handle = _DaytonaHandle(
        client=client,
        sandbox_id="sb-1",
        worktree_path=Path("/workspace"),
        host_worktree_path=Path("/host"),
        baseline={},
    )
    handle.copy_file_in(src, Path("/workspace/dst.bin"))
    _args, kwargs = client.post.call_args
    cmd = kwargs["json"]["command"]
    expected_b64 = base64.b64encode(b"\x00\x01\x02\x03").decode("ascii")
    assert expected_b64 in cmd
    assert "/workspace/dst.bin" in cmd


def test_handle_copy_file_in_raises_exec_failed_on_nonzero(tmp_path: Path) -> None:
    from eden.sandboxes.daytona import _DaytonaHandle

    src = tmp_path / "payload.bin"
    src.write_bytes(b"x")
    client = mock_client({"stdout": "", "stderr": "boom", "exit_code": 1})
    handle = _DaytonaHandle(
        client=client,
        sandbox_id="sb-1",
        worktree_path=Path("/workspace"),
        host_worktree_path=Path("/host"),
        baseline={},
    )
    with pytest.raises(ExecFailed):
        handle.copy_file_in(src, Path("/workspace/dst"))


def test_handle_close_deletes_sandbox() -> None:
    from eden.sandboxes.daytona import _DaytonaHandle

    client = MagicMock(spec=RestClient)
    handle = _DaytonaHandle(
        client=client,
        sandbox_id="sb-1",
        worktree_path=Path("/workspace"),
        host_worktree_path=Path("/host"),
        baseline={},
    )
    handle.close()
    client.delete.assert_called_once_with("/api/sandbox/sb-1")
    client.close.assert_called_once()


def test_handle_close_idempotent_on_not_found() -> None:
    from eden.errors import RestNotFoundError
    from eden.sandboxes.daytona import _DaytonaHandle

    client = MagicMock(spec=RestClient)
    client.delete.side_effect = RestNotFoundError(
        message="404",
        status=404,
        url="https://x/api/sandbox/sb-1",
    )
    handle = _DaytonaHandle(
        client=client,
        sandbox_id="sb-1",
        worktree_path=Path("/workspace"),
        host_worktree_path=Path("/host"),
        baseline={},
    )
    handle.close()  # must not raise
    client.close.assert_called_once()
