"""Verify the docker provider with mocked subprocess + shutil.which."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from eden.providers._types import CreateOptions, Mount
from eden.sandboxes import docker as docker_mod
from eden.sandboxes.errors import (
    ContainerStartFailed,
    ImageNotFound,
    ProviderUnavailable,
)

pytestmark = pytest.mark.unit

_skip_on_windows = pytest.mark.skipif(
    sys.platform == "win32",
    reason="asserts POSIX `-v` argv shape; Windows host paths use `--mount` "
    "(covered by test_windows_host_paths_use_mount_flag)",
)


@dataclass
class _Recorded:
    argv: tuple[str, ...]
    stdout: str
    stderr: str
    returncode: int


@dataclass
class _SubprocessFake:
    queue: list[tuple[str, str, int]] = field(default_factory=list)
    calls: list[_Recorded] = field(default_factory=list)
    which_returns: str | None = "/usr/bin/docker"

    def queue_run(self, stdout: str = "", stderr: str = "", returncode: int = 0) -> None:
        self.queue.append((stdout, stderr, returncode))

    def run(self, argv: list[str], *args: Any, **kwargs: Any) -> Any:
        if not self.queue:
            raise AssertionError(f"unexpected subprocess.run({argv!r})")
        out, err, rc = self.queue.pop(0)
        rec = _Recorded(argv=tuple(argv), stdout=out, stderr=err, returncode=rc)
        self.calls.append(rec)
        return subprocess.CompletedProcess(args=argv, returncode=rc, stdout=out, stderr=err)


@pytest.fixture
def fake_subprocess(monkeypatch: pytest.MonkeyPatch) -> _SubprocessFake:
    fake = _SubprocessFake()
    monkeypatch.setattr(
        "eden.providers._impl.container.shutil.which",
        lambda name: fake.which_returns,
    )
    monkeypatch.setattr("eden.providers._impl.container.subprocess.run", fake.run)
    return fake


def _opts(tmp_path: Path) -> CreateOptions:
    return CreateOptions(
        branch="feat/x",
        worktree_path=tmp_path,
        host_repo_path=tmp_path,
        env={"USER_KEY": "u"},
        mounts=(),
        name_hint="hint",
    )


def test_provider_metadata() -> None:
    p = docker_mod.provider(image="alpine:3.20")
    assert p.name == "docker"
    assert p.kind == "bind_mount"


def test_create_raises_when_docker_missing(
    tmp_path: Path, fake_subprocess: _SubprocessFake
) -> None:
    fake_subprocess.which_returns = None
    p = docker_mod.provider(image="alpine:3.20")
    with pytest.raises(ProviderUnavailable):
        p.create(_opts(tmp_path))


def test_create_raises_when_image_missing(tmp_path: Path, fake_subprocess: _SubprocessFake) -> None:
    fake_subprocess.queue_run(stderr="No such image", returncode=1)  # docker image inspect
    p = docker_mod.provider(image="alpine:3.20")
    with pytest.raises(ImageNotFound) as excinfo:
        p.create(_opts(tmp_path))
    assert excinfo.value.image == "alpine:3.20"


def test_create_raises_when_run_fails(tmp_path: Path, fake_subprocess: _SubprocessFake) -> None:
    fake_subprocess.queue_run(returncode=0)  # image inspect (existence)
    fake_subprocess.queue_run(returncode=0)  # image inspect (UID format) — empty skips check
    fake_subprocess.queue_run(stderr="cannot start", returncode=125)  # docker run fails
    p = docker_mod.provider(image="alpine:3.20")
    with pytest.raises(ContainerStartFailed) as excinfo:
        p.create(_opts(tmp_path))
    assert excinfo.value.exit_code == 125


@_skip_on_windows
def test_create_builds_expected_argv(tmp_path: Path, fake_subprocess: _SubprocessFake) -> None:
    fake_subprocess.queue_run(returncode=0)  # inspect (existence)
    fake_subprocess.queue_run(returncode=0)  # inspect (UID format) — empty skips check
    fake_subprocess.queue_run(stdout="cid123\n", returncode=0)  # run
    p = docker_mod.provider(
        image="alpine:3.20",
        env={"PROVIDER_KEY": "v"},
        network="bridge",
    )
    handle = p.create(_opts(tmp_path))
    assert handle.worktree_path == Path("/workspace")

    run_call = fake_subprocess.calls[2]
    assert run_call.argv[:5] == ("docker", "run", "-d", "--rm", "-i")
    # contains workspace bind (with default :z SELinux relabel)
    assert any(f"{tmp_path}:/workspace:z" == a for a in run_call.argv)
    # contains both env vars
    joined = " ".join(run_call.argv)
    assert "PROVIDER_KEY=v" in joined
    assert "USER_KEY=u" in joined
    # network
    assert "bridge" in run_call.argv
    # entrypoint sleep + image + infinity argument tail
    assert "--entrypoint" in run_call.argv
    assert "sleep" in run_call.argv
    assert run_call.argv[-2] == "alpine:3.20"
    assert run_call.argv[-1] == "infinity"


@_skip_on_windows
def test_provider_mount_overrides_caller_mount(
    tmp_path: Path, fake_subprocess: _SubprocessFake
) -> None:
    fake_subprocess.queue_run(returncode=0)  # inspect (existence)
    fake_subprocess.queue_run(returncode=0)  # inspect (UID format)
    fake_subprocess.queue_run(stdout="cid\n", returncode=0)
    caller_mount = Mount(host=tmp_path / "a", sandbox=Path("/data"))
    provider_mount = Mount(host=tmp_path / "b", sandbox=Path("/data"), read_only=True)
    p = docker_mod.provider(image="alpine:3.20", mounts=(provider_mount,))
    p.create(
        CreateOptions(
            branch="feat/x",
            worktree_path=tmp_path,
            host_repo_path=tmp_path,
            env={},
            mounts=(caller_mount,),
            name_hint=None,
        )
    )
    run_argv = fake_subprocess.calls[2].argv
    # Provider override wins -> /data should map to b, not a.
    bind_strings = [run_argv[i + 1] for i, a in enumerate(run_argv) if a == "-v"]
    matching = [s for s in bind_strings if ":/data:" in s and "ro" in s.split(":")[-1]]
    assert matching, f"expected /data bind with ro, got {bind_strings!r}"
    assert any(str(tmp_path / "b") in s for s in matching)
    assert not any(str(tmp_path / "a") in s for s in bind_strings)


def test_handle_exec_uses_docker_exec(
    tmp_path: Path,
    fake_subprocess: _SubprocessFake,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_subprocess.queue_run(returncode=0)  # inspect (existence)
    fake_subprocess.queue_run(returncode=0)  # inspect (UID format)
    fake_subprocess.queue_run(stdout="cid123\n", returncode=0)
    p = docker_mod.provider(image="alpine:3.20")
    handle = p.create(_opts(tmp_path))

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


def test_handle_close_calls_docker_kill(tmp_path: Path, fake_subprocess: _SubprocessFake) -> None:
    fake_subprocess.queue_run(returncode=0)  # inspect (existence)
    fake_subprocess.queue_run(returncode=0)  # inspect (UID format)
    fake_subprocess.queue_run(stdout="cid123\n", returncode=0)
    fake_subprocess.queue_run(returncode=0)  # docker kill
    p = docker_mod.provider(image="alpine:3.20")
    handle = p.create(_opts(tmp_path))
    handle.close()
    kill_call = fake_subprocess.calls[3]
    assert kill_call.argv == ("docker", "kill", "cid123")


def test_handle_close_swallows_no_such_container(
    tmp_path: Path, fake_subprocess: _SubprocessFake
) -> None:
    fake_subprocess.queue_run(returncode=0)
    fake_subprocess.queue_run(returncode=0)  # UID inspect
    fake_subprocess.queue_run(stdout="cid123\n", returncode=0)
    fake_subprocess.queue_run(stderr="Error: No such container: cid123", returncode=1)
    p = docker_mod.provider(image="alpine:3.20")
    handle = p.create(_opts(tmp_path))
    handle.close()  # must not raise


def test_handle_copy_in_invokes_docker_cp(tmp_path: Path, fake_subprocess: _SubprocessFake) -> None:
    fake_subprocess.queue_run(returncode=0)
    fake_subprocess.queue_run(returncode=0)  # UID inspect
    fake_subprocess.queue_run(stdout="cid123\n", returncode=0)
    fake_subprocess.queue_run(returncode=0)  # docker cp
    p = docker_mod.provider(image="alpine:3.20")
    handle = p.create(_opts(tmp_path))
    handle.copy_file_in(tmp_path / "x", Path("/sandbox/y"))
    cp_call = fake_subprocess.calls[3]
    assert cp_call.argv[0:2] == ("docker", "cp")
    assert cp_call.argv[-1] == "cid123:/sandbox/y"


def test_handle_copy_out_invokes_docker_cp(
    tmp_path: Path, fake_subprocess: _SubprocessFake
) -> None:
    fake_subprocess.queue_run(returncode=0)
    fake_subprocess.queue_run(returncode=0)  # UID inspect
    fake_subprocess.queue_run(stdout="cid123\n", returncode=0)
    fake_subprocess.queue_run(returncode=0)
    p = docker_mod.provider(image="alpine:3.20")
    handle = p.create(_opts(tmp_path))
    handle.copy_file_out(Path("/sandbox/y"), tmp_path / "x")
    cp_call = fake_subprocess.calls[3]
    assert cp_call.argv[0:2] == ("docker", "cp")
    assert cp_call.argv[2] == "cid123:/sandbox/y"
