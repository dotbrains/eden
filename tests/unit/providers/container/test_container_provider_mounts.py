"""Container provider mount and sandbox path behavior."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from eden.providers._impl.container import make_container_provider
from eden.providers._types import Mount
from eden.sandboxes.errors import MountHostMissing
from tests.unit.providers.container.container_provider_helpers import (
    find_run,
    opts,
    skip_on_windows,
)

pytestmark = pytest.mark.unit


@skip_on_windows
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
    p.create(opts(tmp_path))
    run_cmd = find_run(captured)
    bind_specs = [run_cmd[i + 1] for i, a in enumerate(run_cmd) if a == "-v"]
    assert any(f"{tmp_path}:/workspace:z" == arg for arg in bind_specs)


@skip_on_windows
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
    (tmp_path / "extra").mkdir()
    extra = (Mount(host=tmp_path / "extra", sandbox=Path("/extra"), read_only=True),)
    p = make_container_provider(binary=binary, image="alpine", mounts=extra)  # type: ignore[arg-type]
    p.create(opts(tmp_path))
    run_cmd = find_run(captured)
    # default selinux_label="z" → ":ro,z"
    bind_specs = [run_cmd[i + 1] for i, a in enumerate(run_cmd) if a == "-v"]
    assert any(f"{tmp_path / 'extra'}:/extra:ro,z" == arg for arg in bind_specs)


@skip_on_windows
@pytest.mark.parametrize("binary", ["docker", "podman"])
def test_tilde_in_sandbox_path_expands_to_sandbox_homedir(
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
    (tmp_path / "cache").mkdir()
    extra = (Mount(host=tmp_path / "cache", sandbox=Path("~/.npm")),)
    p = make_container_provider(binary=binary, image="alpine", mounts=extra)  # type: ignore[arg-type]
    p.create(opts(tmp_path))
    run_cmd = find_run(captured)
    bind_specs = [run_cmd[i + 1] for i, a in enumerate(run_cmd) if a == "-v"]
    # Expanded to /home/agent/.npm with default selinux label
    assert any(s == f"{tmp_path / 'cache'}:/home/agent/.npm:z" for s in bind_specs), bind_specs


@skip_on_windows
@pytest.mark.parametrize("binary", ["docker", "podman"])
def test_relative_sandbox_path_resolves_under_workspace(
    binary: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("eden.providers._impl.container.shutil.which", lambda _b: "/usr/bin/fake")
    captured: list[list[str]] = []

    def _run(cmd: list[str], *args: object, **kwargs: object) -> MagicMock:
        captured.append(list(cmd))
        m = MagicMock()
        m.returncode = 0
        m.stdout = "container-id\n"
        m.stderr = ""
        return m

    monkeypatch.setattr("eden.providers._impl.container.subprocess.run", _run)
    (tmp_path / "data").mkdir()
    extra = (Mount(host=tmp_path / "data", sandbox=Path("data")),)
    p = make_container_provider(binary=binary, image="alpine", mounts=extra)  # type: ignore[arg-type]
    p.create(opts(tmp_path))
    run_cmd = find_run(captured)
    bind_specs = [run_cmd[i + 1] for i, a in enumerate(run_cmd) if a == "-v"]
    assert any(s == f"{tmp_path / 'data'}:/workspace/data:z" for s in bind_specs), bind_specs


@pytest.mark.parametrize("binary", ["docker", "podman"])
def test_missing_mount_host_path_fails_before_container_run(
    binary: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("eden.providers._impl.container.shutil.which", lambda _b: "/usr/bin/fake")
    captured: list[list[str]] = []

    def _run(cmd: list[str], *args: object, **kwargs: object) -> MagicMock:
        captured.append(list(cmd))
        m = MagicMock()
        m.returncode = 0
        m.stdout = ""
        return m

    monkeypatch.setattr("eden.providers._impl.container.subprocess.run", _run)
    missing = tmp_path / "missing"
    extra = (Mount(host=missing, sandbox=Path("/missing")),)
    p = make_container_provider(binary=binary, image="alpine", mounts=extra)  # type: ignore[arg-type]

    with pytest.raises(MountHostMissing) as excinfo:
        p.create(opts(tmp_path))

    assert excinfo.value.host_path == missing
    assert not any(cmd[1] == "run" for cmd in captured)
