"""Container provider Windows mount and file-mount parent behavior."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from eden.providers._impl.container import make_container_provider
from eden.providers._types import Mount
from tests.unit.providers.container.container_provider_helpers import find_run, opts

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("binary", ["docker", "podman"])
def test_windows_host_paths_use_mount_flag(
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

    monkeypatch.setattr("eden.providers._impl.container_run_args.Path.exists", lambda _p: True)
    monkeypatch.setattr("eden.providers._impl.container.subprocess.run", _run)
    extra = (
        Mount(host=Path("C:/Users/me/cache"), sandbox=Path("/home/agent/.cache"), read_only=True),
    )
    p = make_container_provider(binary=binary, image="alpine", mounts=extra)  # type: ignore[arg-type]
    p.create(opts(tmp_path))

    run_cmd = find_run(captured)
    mount_specs = [run_cmd[i + 1] for i, a in enumerate(run_cmd) if a == "--mount"]
    assert "type=bind,source=C:/Users/me/cache,target=/home/agent/.cache,readonly" in mount_specs


@pytest.mark.parametrize("binary", ["docker", "podman"])
def test_windows_host_paths_resolve_relative_sandbox_path(
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

    monkeypatch.setattr("eden.providers._impl.container_run_args.Path.exists", lambda _p: True)
    monkeypatch.setattr("eden.providers._impl.container.subprocess.run", _run)
    extra = (Mount(host=Path("C:/Users/me/cache"), sandbox=Path("cache"), read_only=True),)
    p = make_container_provider(binary=binary, image="alpine", mounts=extra)  # type: ignore[arg-type]
    p.create(opts(tmp_path))

    run_cmd = find_run(captured)
    mount_specs = [run_cmd[i + 1] for i, a in enumerate(run_cmd) if a == "--mount"]
    assert "type=bind,source=C:/Users/me/cache,target=/workspace/cache,readonly" in mount_specs


@pytest.mark.parametrize("binary", ["docker", "podman"])
def test_create_runs_mkdir_chown_for_file_mount_parent(
    binary: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``_create`` issues a mkdir -p + chown helper exec for each file-mount parent."""
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

    cfg_file = tmp_path / "hosts.yml"
    cfg_file.write_text("x")
    extra = (Mount(host=cfg_file, sandbox=Path("/home/agent/.config/gh/hosts.yml")),)

    p = make_container_provider(binary=binary, image="alpine", mounts=extra)  # type: ignore[arg-type]
    p.create(opts(tmp_path))

    helper_calls = [c for c in captured if len(c) >= 6 and c[1] == "exec" and "--user" in c]
    assert helper_calls, f"no helper exec call in captured: {captured!r}"
    helper = helper_calls[0]
    assert helper[helper.index("--user") + 1] == "0:0"
    joined = " ".join(helper)
    assert "/home/agent/.config/gh" in joined
    assert "mkdir -p" in joined
    assert "chown" in joined


@pytest.mark.parametrize("binary", ["docker", "podman"])
def test_mkdir_helper_failure_kills_container(
    binary: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the parent-prep helper fails, the half-started container is killed."""
    from eden.sandboxes.errors import ContainerStartFailed

    monkeypatch.setattr("eden.providers._impl.container.shutil.which", lambda _b: "/usr/bin/fake")
    captured: list[list[str]] = []

    def _run(cmd: list[str], *args: object, **kwargs: object) -> MagicMock:
        captured.append(list(cmd))
        m = MagicMock()
        # Existence inspect, UID inspect, run all succeed.
        if cmd[1:3] == ["image", "inspect"] or cmd[1] == "run":
            m.returncode = 0
            m.stdout = "container-id\n" if cmd[1] == "run" else ""
            m.stderr = ""
        elif cmd[1] == "exec" and "--user" in cmd:
            m.returncode = 1
            m.stdout = ""
            m.stderr = "permission denied"
        else:
            m.returncode = 0
            m.stdout = ""
        return m

    monkeypatch.setattr("eden.providers._impl.container.subprocess.run", _run)

    cfg = tmp_path / "x.cfg"
    cfg.write_text("x")
    mounts = (Mount(host=cfg, sandbox=Path("/home/agent/.config/gh/x.yml")),)
    p = make_container_provider(binary=binary, image="alpine", mounts=mounts)  # type: ignore[arg-type]

    with pytest.raises(ContainerStartFailed) as ex:
        p.create(opts(tmp_path))
    assert "permission denied" in ex.value.stderr

    kill_calls = [c for c in captured if c[1] == "kill"]
    assert kill_calls, f"expected a kill call to clean up, got: {captured!r}"
