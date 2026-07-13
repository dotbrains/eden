"""Verify container provider creation and image failure paths."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from eden.providers._impl.container import make_container_provider
from eden.sandboxes.errors import ImageNotFound, ProviderUnavailable
from tests.unit.providers.container.container_provider_helpers import find_run, opts

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("binary", ["docker", "podman"])
def test_provider_kind_and_name(binary: str) -> None:
    provider = make_container_provider(binary=binary, image="alpine:latest")  # type: ignore[arg-type]
    assert provider.name == binary
    assert provider.kind == "bind_mount"


@pytest.mark.parametrize("binary", ["docker", "podman"])
def test_create_uses_binary_in_run_argv(
    binary: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "eden.providers._impl.container.shutil.which",
        lambda _binary: "/usr/bin/fake",
    )
    captured: list[list[str]] = []

    def _run(cmd: list[str], *args: object, **kwargs: object) -> MagicMock:
        captured.append(list(cmd))
        result = MagicMock()
        result.returncode = 0
        result.stdout = "container-id-123\n"
        result.stderr = ""
        return result

    monkeypatch.setattr("eden.providers._impl.container.subprocess.run", _run)

    provider = make_container_provider(binary=binary, image="alpine:latest")  # type: ignore[arg-type]
    provider.create(opts(tmp_path))

    inspect_cmd = captured[0]
    run_cmd = find_run(captured)
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
    monkeypatch.setattr("eden.providers._impl.container.shutil.which", lambda _binary: None)
    provider = make_container_provider(binary=binary, image="alpine")  # type: ignore[arg-type]
    with pytest.raises(ProviderUnavailable) as excinfo:
        provider.create(opts(tmp_path))
    assert excinfo.value.provider == binary


@pytest.mark.parametrize("binary", ["docker", "podman"])
def test_image_not_found_error(
    binary: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "eden.providers._impl.container.shutil.which",
        lambda _binary: "/usr/bin/fake",
    )

    def _inspect_fails(cmd: list[str], *args: object, **kwargs: object) -> MagicMock:
        result = MagicMock()
        result.returncode = 1
        result.stdout = ""
        result.stderr = "Error: No such image"
        return result

    monkeypatch.setattr("eden.providers._impl.container.subprocess.run", _inspect_fails)
    provider = make_container_provider(binary=binary, image="missing:tag")  # type: ignore[arg-type]
    with pytest.raises(ImageNotFound):
        provider.create(opts(tmp_path))
