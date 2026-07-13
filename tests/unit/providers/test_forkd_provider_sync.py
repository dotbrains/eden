"""forkd provider copy, close, and finalize behavior."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path

import pytest

from eden.sandboxes.errors import ExecFailed
from tests.unit.forkd_provider_helpers import FakeCommands, FakeResult, FakeSandbox, handle

pytestmark = pytest.mark.unit


def test_handle_copy_file_in_base64_shells(tmp_path: Path) -> None:
    src = tmp_path / "payload.bin"
    src.write_bytes(b"\x00\x01\x02\x03")
    commands = FakeCommands(results=[FakeResult(exit_code=0)])
    sandbox = FakeSandbox(commands=commands)
    h = handle(sandbox, host=tmp_path)
    h.copy_file_in(src, Path("/workspace/dst.bin"))  # type: ignore[attr-defined]
    cmd = commands.calls[0]["cmd"]
    assert isinstance(cmd, str)
    assert base64.b64encode(b"\x00\x01\x02\x03").decode("ascii") in cmd
    assert "/workspace/dst.bin" in cmd


def test_handle_copy_file_in_quotes_paths_with_metacharacters(tmp_path: Path) -> None:
    """Paths with shell metacharacters are shlex-quoted, not interpolated raw."""
    src = tmp_path / "payload.bin"
    src.write_bytes(b"x")
    commands = FakeCommands(results=[FakeResult(exit_code=0)])
    sandbox = FakeSandbox(commands=commands)
    h = handle(sandbox, host=tmp_path)
    h.copy_file_in(src, Path("/workspace/a b; rm -rf x/dst.bin"))  # type: ignore[attr-defined]
    cmd = commands.calls[0]["cmd"]
    assert isinstance(cmd, str)
    assert "mkdir -p '/workspace/a b; rm -rf x' &&" in cmd
    assert "> '/workspace/a b; rm -rf x/dst.bin'" in cmd


def test_handle_copy_file_out_quotes_path(tmp_path: Path) -> None:
    commands = FakeCommands(results=[FakeResult(stdout="", exit_code=0)])
    sandbox = FakeSandbox(commands=commands)
    h = handle(sandbox, host=tmp_path)
    h.copy_file_out(Path("/workspace/odd name.txt"), tmp_path / "out.txt")  # type: ignore[attr-defined]
    cmd = commands.calls[0]["cmd"]
    assert isinstance(cmd, str)
    assert cmd == "base64 '/workspace/odd name.txt'"


def test_handle_copy_file_in_raises_exec_failed_on_nonzero(tmp_path: Path) -> None:
    src = tmp_path / "payload.bin"
    src.write_bytes(b"x")
    commands = FakeCommands(results=[FakeResult(stderr="boom", exit_code=1)])
    sandbox = FakeSandbox(commands=commands)
    h = handle(sandbox, host=tmp_path)
    with pytest.raises(ExecFailed):
        h.copy_file_in(src, Path("/workspace/dst"))  # type: ignore[attr-defined]


def test_handle_close_kills_sandbox(tmp_path: Path) -> None:
    sandbox = FakeSandbox(commands=FakeCommands(results=[]))
    h = handle(sandbox, host=tmp_path)
    h.close()  # type: ignore[attr-defined]
    assert sandbox.killed is True


def test_handle_close_never_raises(tmp_path: Path) -> None:
    @dataclass
    class _RaisingSandbox:
        commands: FakeCommands

        def kill(self) -> None:
            raise RuntimeError("teardown failed")

    sandbox = _RaisingSandbox(commands=FakeCommands(results=[]))
    h = handle(sandbox, host=tmp_path)  # type: ignore[arg-type]
    h.close()  # type: ignore[attr-defined]  # must not raise


def test_finalize_no_changes_returns_applied_true(tmp_path: Path) -> None:
    commands = FakeCommands(results=[FakeResult(stdout="", exit_code=0)])
    sandbox = FakeSandbox(commands=commands)
    h = handle(sandbox, host=tmp_path, baseline={})
    fr = h.finalize(target=tmp_path)  # type: ignore[attr-defined]
    assert fr.applied is True
    assert fr.files_changed == ()


def test_finalize_pulls_added_files_to_target(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    commands = FakeCommands(
        results=[
            FakeResult(stdout="abc123  ./new.txt\n", exit_code=0),
            FakeResult(stdout=base64.b64encode(b"hello").decode("ascii"), exit_code=0),
        ]
    )
    sandbox = FakeSandbox(commands=commands)
    h = handle(sandbox, host=target, baseline={})
    fr = h.finalize(target=target)  # type: ignore[attr-defined]
    assert fr.applied is True
    assert (target / "new.txt").read_bytes() == b"hello"
    assert Path("new.txt") in fr.files_changed


def test_finalize_propagates_deletes(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "gone.txt").write_text("bye", encoding="utf-8")
    commands = FakeCommands(results=[FakeResult(stdout="", exit_code=0)])
    sandbox = FakeSandbox(commands=commands)
    h = handle(sandbox, host=target, baseline={Path("gone.txt"): "old"})
    fr = h.finalize(target=target)  # type: ignore[attr-defined]
    assert fr.applied is True
    assert not (target / "gone.txt").exists()
