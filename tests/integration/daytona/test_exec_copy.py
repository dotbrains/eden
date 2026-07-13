"""Daytona live-API exec and file transfer integration tests."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from eden.providers._protocols import IsolatedSandboxHandle

pytestmark = pytest.mark.integration


def test_initial_upload_visible_in_sandbox(
    daytona_handle: IsolatedSandboxHandle,
) -> None:
    """Files present in the host worktree at create-time land in /workspace."""
    result = daytona_handle.exec("cat /workspace/seed.txt")
    assert result.exit_code == 0, result.stderr
    assert "hello from host" in result.stdout


def test_exec_returns_stdout_and_exit_code(
    daytona_handle: IsolatedSandboxHandle,
) -> None:
    result = daytona_handle.exec("printf hello && exit 0")
    assert result.exit_code == 0
    assert "hello" in result.stdout


def test_exec_nonzero_exit_propagates(
    daytona_handle: IsolatedSandboxHandle,
) -> None:
    result = daytona_handle.exec("exit 7")
    assert result.exit_code == 7


def test_exec_with_stdin_payload(
    daytona_handle: IsolatedSandboxHandle,
) -> None:
    """The base64-wrap path used to feed stdin to a remote shell command."""
    result = daytona_handle.exec("cat", stdin="payload-via-stdin\n")
    assert result.exit_code == 0
    assert "payload-via-stdin" in result.stdout


def test_copy_file_in_round_trip(
    daytona_handle: IsolatedSandboxHandle,
    tmp_path: Path,
) -> None:
    src = tmp_path / "in.txt"
    src.write_text("copy_in worked\n")
    target = Path("/workspace/copies/in.txt")  # parent doesn't exist yet
    daytona_handle.copy_file_in(src, target)

    result = daytona_handle.exec(f"cat {target.as_posix()}")
    assert result.exit_code == 0
    assert "copy_in worked" in result.stdout


def test_copy_file_in_directory(
    daytona_handle: IsolatedSandboxHandle,
    tmp_path: Path,
) -> None:
    """Directory upload uses the tar+base64 helper shared with Vercel."""
    src_dir = tmp_path / "fixtures"
    src_dir.mkdir()
    (src_dir / "a.txt").write_text("alpha\n")
    (src_dir / "nested").mkdir()
    (src_dir / "nested" / "b.txt").write_text("beta\n")
    target = Path("/workspace/dir-fixture")
    daytona_handle.copy_file_in(src_dir, target)

    a = daytona_handle.exec(f"cat {target.as_posix()}/a.txt")
    b = daytona_handle.exec(f"cat {target.as_posix()}/nested/b.txt")
    assert "alpha" in a.stdout
    assert "beta" in b.stdout


def test_copy_file_out_round_trip(
    daytona_handle: IsolatedSandboxHandle,
    tmp_path: Path,
) -> None:
    # Create a file in the sandbox, then pull it back to the host.
    sandbox_path = Path(f"/workspace/out-{uuid.uuid4().hex[:6]}.txt")
    write = daytona_handle.exec(
        f"printf 'copy_out worked' > {sandbox_path.as_posix()}",
    )
    assert write.exit_code == 0, write.stderr

    dest = tmp_path / "out.txt"
    daytona_handle.copy_file_out(sandbox_path, dest)
    assert dest.read_text() == "copy_out worked"
