"""Verify make_container_provider — argv shapes for docker + podman.

Tests are parametrized over the binary so one suite covers both providers.
All subprocess calls are mocked; no docker/podman binary required to run.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from eden.providers._impl.container import make_container_provider
from eden.providers._types import CreateOptions, Mount
from eden.sandboxes.errors import (
    ContainerStartFailed,
    ImageNotFound,
    ProviderUnavailable,
)

pytestmark = pytest.mark.unit


def _opts(tmp_path: Path) -> CreateOptions:
    return CreateOptions(
        branch="HEAD",
        worktree_path=tmp_path,
        host_repo_path=tmp_path,
        env={},
        mounts=(),
        name_hint="test",
    )


@pytest.mark.parametrize("binary", ["docker", "podman"])
def test_provider_kind_and_name(binary: str) -> None:
    p = make_container_provider(binary=binary, image="alpine:latest")  # type: ignore[arg-type]
    assert p.name == binary
    assert p.kind == "bind_mount"


@pytest.mark.parametrize("binary", ["docker", "podman"])
def test_create_uses_binary_in_run_argv(
    binary: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("eden.providers._impl.container.shutil.which", lambda _b: "/usr/bin/fake")
    captured: list[list[str]] = []

    def _run(cmd: list[str], *args: object, **kwargs: object) -> MagicMock:
        captured.append(list(cmd))
        m = MagicMock()
        m.returncode = 0
        m.stdout = "container-id-123\n"
        m.stderr = ""
        return m

    monkeypatch.setattr("eden.providers._impl.container.subprocess.run", _run)

    p = make_container_provider(binary=binary, image="alpine:latest")  # type: ignore[arg-type]
    p.create(_opts(tmp_path))

    inspect_cmd = captured[0]
    run_cmd = captured[1]
    assert inspect_cmd[0] == binary
    assert inspect_cmd[1:4] == ["image", "inspect", "alpine:latest"]
    assert run_cmd[0] == binary
    assert "run" in run_cmd
    assert "-d" in run_cmd
    assert "--rm" in run_cmd
    assert "alpine:latest" in run_cmd


@pytest.mark.parametrize("binary", ["docker", "podman"])
def test_provider_missing_binary_raises(
    binary: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("eden.providers._impl.container.shutil.which", lambda _b: None)
    p = make_container_provider(binary=binary, image="alpine")  # type: ignore[arg-type]
    with pytest.raises(ProviderUnavailable) as excinfo:
        p.create(_opts(tmp_path))
    assert excinfo.value.provider == binary


@pytest.mark.parametrize("binary", ["docker", "podman"])
def test_image_not_found_error(
    binary: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("eden.providers._impl.container.shutil.which", lambda _b: "/usr/bin/fake")

    def _inspect_fails(cmd: list[str], *args: object, **kwargs: object) -> MagicMock:
        m = MagicMock()
        m.returncode = 1
        m.stdout = ""
        m.stderr = "Error: No such image"
        return m

    monkeypatch.setattr("eden.providers._impl.container.subprocess.run", _inspect_fails)
    p = make_container_provider(binary=binary, image="missing:tag")  # type: ignore[arg-type]
    with pytest.raises(ImageNotFound):
        p.create(_opts(tmp_path))


@pytest.mark.parametrize("binary", ["docker", "podman"])
def test_container_start_failed(
    binary: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("eden.providers._impl.container.shutil.which", lambda _b: "/usr/bin/fake")

    def _run(cmd: list[str], *args: object, **kwargs: object) -> MagicMock:
        m = MagicMock()
        if "image" in cmd and "inspect" in cmd:
            m.returncode = 0
        else:
            m.returncode = 125
            m.stderr = "boom"
        m.stdout = ""
        return m

    monkeypatch.setattr("eden.providers._impl.container.subprocess.run", _run)
    p = make_container_provider(binary=binary, image="alpine")  # type: ignore[arg-type]
    with pytest.raises(ContainerStartFailed) as excinfo:
        p.create(_opts(tmp_path))
    assert excinfo.value.exit_code == 125


@pytest.mark.parametrize("binary", ["docker", "podman"])
def test_implicit_workspace_mount(
    binary: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("eden.providers._impl.container.shutil.which", lambda _b: "/usr/bin/fake")
    captured: list[list[str]] = []

    def _run(cmd: list[str], *args: object, **kwargs: object) -> MagicMock:
        captured.append(list(cmd))
        m = MagicMock()
        m.returncode = 0
        m.stdout = "container-id\n"
        return m

    monkeypatch.setattr("eden.providers._impl.container.subprocess.run", _run)
    p = make_container_provider(binary=binary, image="alpine")  # type: ignore[arg-type]
    p.create(_opts(tmp_path))
    run_cmd = captured[1]
    assert any(f"{tmp_path}:/workspace" in arg for arg in run_cmd)


@pytest.mark.parametrize("binary", ["docker", "podman"])
def test_provider_mounts_threaded(
    binary: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("eden.providers._impl.container.shutil.which", lambda _b: "/usr/bin/fake")
    captured: list[list[str]] = []

    def _run(cmd: list[str], *args: object, **kwargs: object) -> MagicMock:
        captured.append(list(cmd))
        m = MagicMock()
        m.returncode = 0
        m.stdout = "container-id\n"
        return m

    monkeypatch.setattr("eden.providers._impl.container.subprocess.run", _run)
    extra = (Mount(host=tmp_path / "extra", sandbox=Path("/extra"), read_only=True),)
    p = make_container_provider(binary=binary, image="alpine", mounts=extra)  # type: ignore[arg-type]
    p.create(_opts(tmp_path))
    run_cmd = captured[1]
    assert any(f"{tmp_path / 'extra'}:/extra:ro" in arg for arg in run_cmd)


@pytest.mark.parametrize("binary", ["docker", "podman"])
def test_network_flag_threaded(
    binary: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("eden.providers._impl.container.shutil.which", lambda _b: "/usr/bin/fake")
    captured: list[list[str]] = []

    def _run(cmd: list[str], *args: object, **kwargs: object) -> MagicMock:
        captured.append(list(cmd))
        m = MagicMock()
        m.returncode = 0
        m.stdout = "container-id\n"
        return m

    monkeypatch.setattr("eden.providers._impl.container.subprocess.run", _run)
    p = make_container_provider(binary=binary, image="alpine", network="host")  # type: ignore[arg-type]
    p.create(_opts(tmp_path))
    run_cmd = captured[1]
    idx = run_cmd.index("--network")
    assert run_cmd[idx + 1] == "host"
