"""Verify the docker provider with mocked subprocess + shutil.which."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from eden.providers._types import CreateOptions, Mount
from eden.sandboxes import docker as docker_mod
from eden.sandboxes.errors import (
    ContainerStartFailed,
    ImageNotFound,
    ProviderUnavailable,
)
from tests.unit.docker_provider_helpers import SubprocessFake, opts

pytestmark = pytest.mark.unit
pytest_plugins = ["tests.unit.docker_provider_helpers"]

_skip_on_windows = pytest.mark.skipif(
    sys.platform == "win32",
    reason="asserts POSIX `-v` argv shape; Windows host paths use `--mount` "
    "(covered by test_windows_host_paths_use_mount_flag)",
)


def test_provider_metadata() -> None:
    p = docker_mod.provider(image="alpine:3.20")
    assert p.name == "docker"
    assert p.kind == "bind_mount"


def test_create_raises_when_docker_missing(tmp_path: Path, fake_subprocess: SubprocessFake) -> None:
    fake_subprocess.which_returns = None
    p = docker_mod.provider(image="alpine:3.20")
    with pytest.raises(ProviderUnavailable):
        p.create(opts(tmp_path))


def test_create_raises_when_image_missing(tmp_path: Path, fake_subprocess: SubprocessFake) -> None:
    fake_subprocess.queue_run(stderr="No such image", returncode=1)  # docker image inspect
    p = docker_mod.provider(image="alpine:3.20")
    with pytest.raises(ImageNotFound) as excinfo:
        p.create(opts(tmp_path))
    assert excinfo.value.image == "alpine:3.20"


def test_create_raises_when_run_fails(tmp_path: Path, fake_subprocess: SubprocessFake) -> None:
    fake_subprocess.queue_run(returncode=0)  # image inspect (existence)
    fake_subprocess.queue_run(returncode=0)  # image inspect (UID format) — empty skips check
    fake_subprocess.queue_run(stderr="cannot start", returncode=125)  # docker run fails
    p = docker_mod.provider(image="alpine:3.20")
    with pytest.raises(ContainerStartFailed) as excinfo:
        p.create(opts(tmp_path))
    assert excinfo.value.exit_code == 125


@_skip_on_windows
def test_create_builds_expected_argv(tmp_path: Path, fake_subprocess: SubprocessFake) -> None:
    fake_subprocess.queue_run(returncode=0)  # inspect (existence)
    fake_subprocess.queue_run(returncode=0)  # inspect (UID format) — empty skips check
    fake_subprocess.queue_run(stdout="cid123\n", returncode=0)  # run
    p = docker_mod.provider(
        image="alpine:3.20",
        env={"PROVIDER_KEY": "v"},
        network="bridge",
    )
    handle = p.create(opts(tmp_path))
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
    tmp_path: Path, fake_subprocess: SubprocessFake
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
