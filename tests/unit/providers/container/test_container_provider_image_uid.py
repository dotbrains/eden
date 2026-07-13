"""Container provider image UID checks."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from eden.providers._impl.container import make_container_provider
from eden.sandboxes.errors import ImageUidMismatch
from tests.unit.providers.container.container_provider_helpers import opts

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("binary", ["docker", "podman"])
def test_image_uid_mismatch_raises(
    binary: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("eden.providers._impl.container.shutil.which", lambda _b: "/usr/bin/fake")

    def _run(cmd: list[str], *args: object, **kwargs: object) -> MagicMock:
        m = MagicMock()
        if "image" in cmd and "inspect" in cmd:
            m.returncode = 0
            # Second inspect carries --format and returns a different UID.
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
