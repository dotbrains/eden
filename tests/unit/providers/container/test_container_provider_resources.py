"""Verify container provider resource flag argv shapes."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from eden.providers._impl.container import make_container_provider
from tests.unit.providers.container.container_provider_helpers import find_run, opts

pytestmark = pytest.mark.unit


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
    p.create(opts(tmp_path))
    run_cmd = find_run(captured)
    idx = run_cmd.index("--network")
    assert run_cmd[idx + 1] == "host"


@pytest.mark.parametrize("binary", ["docker", "podman"])
def test_multiple_network_flags_threaded(
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
    p = make_container_provider(
        binary=binary,  # type: ignore[arg-type]
        image="alpine",
        network=("net1", "net2"),
    )
    p.create(opts(tmp_path))
    run_cmd = find_run(captured)
    network_args = [run_cmd[i + 1] for i, a in enumerate(run_cmd) if a == "--network"]
    assert network_args == ["net1", "net2"]


@pytest.mark.parametrize("binary", ["docker", "podman"])
def test_cpus_flag_threaded(binary: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("eden.providers._impl.container.shutil.which", lambda _b: "/usr/bin/fake")
    captured: list[list[str]] = []

    def _run(cmd: list[str], *args: object, **kwargs: object) -> MagicMock:
        captured.append(list(cmd))
        m = MagicMock()
        m.returncode = 0
        m.stdout = "container-id\n"
        return m

    monkeypatch.setattr("eden.providers._impl.container.subprocess.run", _run)
    p = make_container_provider(binary=binary, image="alpine", cpus=1.5)  # type: ignore[arg-type]
    p.create(opts(tmp_path))
    run_cmd = find_run(captured)
    idx = run_cmd.index("--cpus")
    assert run_cmd[idx + 1] == "1.5"


@pytest.mark.parametrize("binary", ["docker", "podman"])
def test_cpus_omitted_when_none(
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
    assert "--cpus" not in run_cmd


@pytest.mark.parametrize("binary", ["docker", "podman"])
def test_devices_threaded_per_entry(
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
    p = make_container_provider(
        binary=binary,  # type: ignore[arg-type]
        image="alpine",
        devices=("/dev/kvm", "/dev/dri:/dev/dri:rwm"),
    )
    p.create(opts(tmp_path))
    run_cmd = find_run(captured)
    device_specs = [run_cmd[i + 1] for i, a in enumerate(run_cmd) if a == "--device"]
    assert "/dev/kvm" in device_specs
    assert "/dev/dri:/dev/dri:rwm" in device_specs


@pytest.mark.parametrize("binary", ["docker", "podman"])
def test_groups_threaded_with_string_and_int(
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
    p = make_container_provider(
        binary=binary,  # type: ignore[arg-type]
        image="alpine",
        groups=("docker", 998),
    )
    p.create(opts(tmp_path))
    run_cmd = find_run(captured)
    group_args = [run_cmd[i + 1] for i, a in enumerate(run_cmd) if a == "--group-add"]
    assert group_args == ["docker", "998"]
