"""Verify docker provider handle methods."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from eden.sandboxes import docker as docker_mod
from tests.unit.docker_provider_helpers import SubprocessFake, opts

pytestmark = pytest.mark.unit
pytest_plugins = ["tests.unit.docker_provider_helpers"]


def test_handle_exec_uses_docker_exec(
    tmp_path: Path,
    fake_subprocess: SubprocessFake,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_subprocess.queue_run(returncode=0)  # inspect (existence)
    fake_subprocess.queue_run(returncode=0)  # inspect (UID format)
    fake_subprocess.queue_run(stdout="cid123\n", returncode=0)
    p = docker_mod.provider(image="alpine:3.20")
    handle = p.create(opts(tmp_path))

    captured: dict[str, Any] = {}

    def fake_stream_exec(argv: list[str], **kwargs: Any) -> Any:
        from eden.providers._types import ExecResult

        captured["argv"] = argv
        captured["kwargs"] = kwargs
        return ExecResult(stdout="ok\n", stderr="", exit_code=0)

    monkeypatch.setattr("eden.providers._impl.container_handle.stream_exec", fake_stream_exec)
    result = handle.exec("echo hi", cwd=Path("/workspace/sub"), env={"K": "V"})
    assert result.exit_code == 0
    argv = captured["argv"]
    assert argv[0:3] == ["docker", "exec", "-i"]
    assert "-w" in argv
    assert "/workspace/sub" in argv
    assert "-e" in argv
    assert "K=V" in argv
    assert "cid123" in argv
    assert argv[-3:] == ["/bin/sh", "-c", "echo hi"]


def test_handle_close_calls_docker_kill(tmp_path: Path, fake_subprocess: SubprocessFake) -> None:
    fake_subprocess.queue_run(returncode=0)  # inspect (existence)
    fake_subprocess.queue_run(returncode=0)  # inspect (UID format)
    fake_subprocess.queue_run(stdout="cid123\n", returncode=0)
    fake_subprocess.queue_run(returncode=0)  # docker kill
    p = docker_mod.provider(image="alpine:3.20")
    handle = p.create(opts(tmp_path))
    handle.close()
    kill_call = fake_subprocess.calls[3]
    assert kill_call.argv == ("docker", "kill", "cid123")


def test_handle_close_swallows_no_such_container(
    tmp_path: Path, fake_subprocess: SubprocessFake
) -> None:
    fake_subprocess.queue_run(returncode=0)
    fake_subprocess.queue_run(returncode=0)  # UID inspect
    fake_subprocess.queue_run(stdout="cid123\n", returncode=0)
    fake_subprocess.queue_run(stderr="Error: No such container: cid123", returncode=1)
    p = docker_mod.provider(image="alpine:3.20")
    handle = p.create(opts(tmp_path))
    handle.close()  # must not raise


def test_handle_copy_in_invokes_docker_cp(tmp_path: Path, fake_subprocess: SubprocessFake) -> None:
    fake_subprocess.queue_run(returncode=0)
    fake_subprocess.queue_run(returncode=0)  # UID inspect
    fake_subprocess.queue_run(stdout="cid123\n", returncode=0)
    fake_subprocess.queue_run(returncode=0)  # docker cp
    p = docker_mod.provider(image="alpine:3.20")
    handle = p.create(opts(tmp_path))
    handle.copy_file_in(tmp_path / "x", Path("/sandbox/y"))
    cp_call = fake_subprocess.calls[3]
    assert cp_call.argv[0:2] == ("docker", "cp")
    assert cp_call.argv[-1] == "cid123:/sandbox/y"


def test_handle_copy_out_invokes_docker_cp(tmp_path: Path, fake_subprocess: SubprocessFake) -> None:
    fake_subprocess.queue_run(returncode=0)
    fake_subprocess.queue_run(returncode=0)  # UID inspect
    fake_subprocess.queue_run(stdout="cid123\n", returncode=0)
    fake_subprocess.queue_run(returncode=0)
    p = docker_mod.provider(image="alpine:3.20")
    handle = p.create(opts(tmp_path))
    handle.copy_file_out(Path("/sandbox/y"), tmp_path / "x")
    cp_call = fake_subprocess.calls[3]
    assert cp_call.argv[0:2] == ("docker", "cp")
    assert cp_call.argv[2] == "cid123:/sandbox/y"
