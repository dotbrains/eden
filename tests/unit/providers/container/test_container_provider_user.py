"""Container provider user, user namespace, and image UID checks."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from eden.providers._impl.container import make_container_provider
from eden.sandboxes.errors import ImageUidMismatch
from tests.unit.providers.container.container_provider_helpers import find_run, opts

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("binary", ["docker", "podman"])
def test_user_flag_defaults_to_host_uid(
    binary: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("eden.providers._impl.container.shutil.which", lambda _b: "/usr/bin/fake")
    monkeypatch.setattr("eden.providers._impl.container._host_uid", lambda: 1234)
    monkeypatch.setattr("eden.providers._impl.container._host_gid", lambda: 5678)
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
    idx = run_cmd.index("--user")
    assert run_cmd[idx + 1] == "1234:5678"


@pytest.mark.parametrize("binary", ["docker", "podman"])
def test_user_flag_explicit_overrides_host(
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
        container_uid=5000,
        container_gid=5001,
    )
    p.create(opts(tmp_path))
    run_cmd = find_run(captured)
    idx = run_cmd.index("--user")
    assert run_cmd[idx + 1] == "5000:5001"


def test_podman_keep_id_userns_flag_threaded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
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
    p = make_container_provider(
        binary="podman",
        image="alpine",
        container_uid=1000,
        container_gid=1001,
        userns="keep-id",
    )
    p.create(opts(tmp_path))
    run_cmd = find_run(captured)
    assert "--userns=keep-id:uid=1000,gid=1001" in run_cmd


def test_podman_userns_can_be_disabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
    p = make_container_provider(
        binary="podman",
        image="alpine",
        container_uid=1000,
        container_gid=1001,
        userns=None,
    )
    p.create(opts(tmp_path))
    run_cmd = find_run(captured)
    assert not any(arg.startswith("--userns=") for arg in run_cmd)


def test_docker_ignores_userns_option(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
    p = make_container_provider(
        binary="docker",
        image="alpine",
        container_uid=1000,
        container_gid=1001,
        userns="keep-id",
    )
    p.create(opts(tmp_path))
    run_cmd = find_run(captured)
    assert not any(arg.startswith("--userns=") for arg in run_cmd)


@pytest.mark.parametrize("binary", ["docker", "podman"])
def test_image_uid_mismatch_raises(
    binary: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("eden.providers._impl.container.shutil.which", lambda _b: "/usr/bin/fake")

    def _run(cmd: list[str], *args: object, **kwargs: object) -> MagicMock:
        m = MagicMock()
        if "image" in cmd and "inspect" in cmd:
            m.returncode = 0
            # Second inspect carries --format and returns a different UID
            if "--format" in cmd:
                m.stdout = "999:999\n"
            else:
                m.stdout = ""
            m.stderr = ""
        else:
            m.returncode = 0
            m.stdout = "container-id\n"
        return m

    monkeypatch.setattr("eden.providers._impl.container.subprocess.run", _run)
    p = make_container_provider(
        binary=binary,  # type: ignore[arg-type]
        image="alpine",
        container_uid=1000,
        container_gid=1000,
    )
    with pytest.raises(ImageUidMismatch) as ex:
        p.create(opts(tmp_path))
    assert ex.value.image_uid == 999
    assert ex.value.expected_uid == 1000


@pytest.mark.parametrize("binary", ["docker", "podman"])
def test_image_uid_check_skipped_for_non_numeric_user(
    binary: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Image with `USER agent` (non-numeric) should not block startup."""
    monkeypatch.setattr("eden.providers._impl.container.shutil.which", lambda _b: "/usr/bin/fake")

    def _run(cmd: list[str], *args: object, **kwargs: object) -> MagicMock:
        m = MagicMock()
        if "image" in cmd and "inspect" in cmd and "--format" in cmd:
            m.returncode = 0
            m.stdout = "agent\n"
        elif "image" in cmd and "inspect" in cmd:
            m.returncode = 0
            m.stdout = ""
        else:
            m.returncode = 0
            m.stdout = "container-id\n"
        m.stderr = ""
        return m

    monkeypatch.setattr("eden.providers._impl.container.subprocess.run", _run)
    p = make_container_provider(
        binary=binary,  # type: ignore[arg-type]
        image="alpine",
        container_uid=1000,
    )
    # Should not raise.
    p.create(opts(tmp_path))


@pytest.mark.parametrize("binary", ["docker", "podman"])
def test_image_uid_check_skipped_when_user_directive_empty(
    binary: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("eden.providers._impl.container.shutil.which", lambda _b: "/usr/bin/fake")

    def _run(cmd: list[str], *args: object, **kwargs: object) -> MagicMock:
        m = MagicMock()
        if "image" in cmd and "inspect" in cmd and "--format" in cmd:
            m.returncode = 0
            m.stdout = "\n"  # no USER directive
        elif "image" in cmd and "inspect" in cmd:
            m.returncode = 0
            m.stdout = ""
        else:
            m.returncode = 0
            m.stdout = "container-id\n"
        m.stderr = ""
        return m

    monkeypatch.setattr("eden.providers._impl.container.subprocess.run", _run)
    p = make_container_provider(binary=binary, image="alpine", container_uid=1000)  # type: ignore[arg-type]
    # Should not raise.
    p.create(opts(tmp_path))
