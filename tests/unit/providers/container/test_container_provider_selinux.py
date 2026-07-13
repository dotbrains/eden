"""Container provider SELinux mount label behavior."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from eden.providers._impl.container import make_container_provider
from eden.providers._types import Mount
from tests.unit.providers.container.container_provider_helpers import (
    find_run,
    opts,
    skip_on_windows,
)

pytestmark = pytest.mark.unit


@skip_on_windows
@pytest.mark.parametrize("binary", ["docker", "podman"])
def test_selinux_label_can_be_disabled(
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
        selinux_label=None,
    )
    p.create(opts(tmp_path))
    run_cmd = find_run(captured)
    # Workspace mount has no SELinux suffix when disabled.
    bind_specs = [run_cmd[i + 1] for i, a in enumerate(run_cmd) if a == "-v"]
    assert any(f"{tmp_path}:/workspace" == arg for arg in bind_specs)
    assert not any(arg.endswith(":z") for arg in run_cmd)
    assert not any(arg.endswith(":Z") for arg in run_cmd)


@skip_on_windows
@pytest.mark.parametrize("binary", ["docker", "podman"])
def test_selinux_label_uppercase_z(
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
        selinux_label="Z",
    )
    p.create(opts(tmp_path))
    run_cmd = find_run(captured)
    assert any(arg.endswith(":Z") for arg in run_cmd)


@skip_on_windows
@pytest.mark.parametrize("binary", ["docker", "podman"])
def test_selinux_label_combines_with_readonly(
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
    extra = (Mount(host=tmp_path / "ro", sandbox=Path("/ro"), read_only=True),)
    p = make_container_provider(
        binary=binary,  # type: ignore[arg-type]
        image="alpine",
        mounts=extra,
        selinux_label="z",
    )
    p.create(opts(tmp_path))
    run_cmd = find_run(captured)
    assert any(f"{tmp_path / 'ro'}:/ro:ro,z" == arg for arg in run_cmd)
