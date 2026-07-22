"""Verify container provider defaults and start failures."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from eden.providers._impl.container import make_container_provider
from eden.providers._impl.container_run_args import build_mount_map
from eden.providers._types import Mount
from eden.sandboxes.errors import ContainerStartFailed
from tests.unit.providers.container.container_provider_helpers import find_run, opts

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("binary", ["docker", "podman"])
def test_image_defaults_from_repo_directory(
    binary: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "eden.providers._impl.container.shutil.which",
        lambda _binary: "/usr/bin/fake",
    )
    captured: list[list[str]] = []
    repo = tmp_path / "My Repo!"
    repo.mkdir()

    def _run(cmd: list[str], *args: object, **kwargs: object) -> MagicMock:
        captured.append(list(cmd))
        result = MagicMock()
        result.returncode = 0
        result.stdout = "container-id\n"
        result.stderr = ""
        return result

    monkeypatch.setattr("eden.providers._impl.container.subprocess.run", _run)
    provider = make_container_provider(binary=binary)  # type: ignore[arg-type]
    provider.create(opts(repo))

    inspect_cmd = captured[0]
    run_cmd = find_run(captured)
    assert inspect_cmd[:4] == [binary, "image", "inspect", "eden:my-repo"]
    assert "eden:my-repo" in run_cmd


def test_build_mount_map_expands_user_mount_host_tilde(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "cache").mkdir()
    mount_map = build_mount_map(
        worktree_path=tmp_path / "repo",
        opts_mounts=(Mount(host=Path("~/cache"), sandbox=Path("/cache")),),
        provider_mounts=(),
    )

    assert mount_map[Path("/cache")].host == tmp_path / "cache"


@pytest.mark.parametrize("binary", ["docker", "podman"])
def test_container_start_failed(
    binary: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "eden.providers._impl.container.shutil.which",
        lambda _binary: "/usr/bin/fake",
    )

    def _run(cmd: list[str], *args: object, **kwargs: object) -> MagicMock:
        result = MagicMock()
        if "image" in cmd and "inspect" in cmd:
            result.returncode = 0
        else:
            result.returncode = 125
            result.stderr = "boom"
        result.stdout = ""
        return result

    monkeypatch.setattr("eden.providers._impl.container.subprocess.run", _run)

    provider = make_container_provider(binary=binary, image="alpine")  # type: ignore[arg-type]
    with pytest.raises(ContainerStartFailed) as excinfo:
        provider.create(opts(tmp_path))
    assert excinfo.value.exit_code == 125
