"""Container provider mount and sandbox path behavior."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from eden.providers._impl.container import make_container_provider
from eden.providers._types import Mount
from eden.sandboxes.errors import MountConfigError
from tests.unit.container_provider_helpers import find_run, opts, skip_on_windows

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
    extra = (Mount(host=tmp_path / "extra", sandbox=Path("/extra"), read_only=True),)
    p = make_container_provider(binary=binary, image="alpine", mounts=extra)  # type: ignore[arg-type]
    p.create(opts(tmp_path))
    run_cmd = find_run(captured)
    # default selinux_label="z" → ":ro,z"
    bind_specs = [run_cmd[i + 1] for i, a in enumerate(run_cmd) if a == "-v"]
    assert any(f"{tmp_path / 'extra'}:/extra:ro,z" == arg for arg in bind_specs)


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
    extra = (Mount(host=tmp_path / "data", sandbox=Path("data")),)
    p = make_container_provider(binary=binary, image="alpine", mounts=extra)  # type: ignore[arg-type]
    p.create(opts(tmp_path))
    run_cmd = find_run(captured)
    bind_specs = [run_cmd[i + 1] for i, a in enumerate(run_cmd) if a == "-v"]
    assert any(s == f"{tmp_path / 'data'}:/workspace/data:z" for s in bind_specs), bind_specs


def test_expand_sandbox_tilde_root() -> None:
    from eden.providers._impl.container_mounts import _expand_sandbox_tilde

    expanded = _expand_sandbox_tilde(Path("~"), sandbox_homedir=Path("/home/agent"))
    assert expanded == Path("/home/agent")


def test_expand_sandbox_tilde_with_subpath() -> None:
    from eden.providers._impl.container_mounts import _expand_sandbox_tilde

    expanded = _expand_sandbox_tilde(Path("~/.config/x"), sandbox_homedir=Path("/home/agent"))
    assert expanded == Path("/home/agent/.config/x")


def test_expand_sandbox_tilde_passthrough_for_absolute() -> None:
    from eden.providers._impl.container_mounts import _expand_sandbox_tilde

    expanded = _expand_sandbox_tilde(Path("/etc/hosts"), sandbox_homedir=Path("/home/agent"))
    assert expanded == Path("/etc/hosts")


def test_expand_sandbox_tilde_resolves_relative_under_workspace() -> None:
    from eden.providers._impl.container_mounts import _expand_sandbox_tilde

    expanded = _expand_sandbox_tilde(Path("cache/npm"), sandbox_homedir=Path("/home/agent"))
    assert expanded == Path("/workspace/cache/npm")


def test_expand_sandbox_tilde_raises_when_homedir_missing() -> None:
    from eden.providers._impl.container_mounts import _expand_sandbox_tilde

    with pytest.raises(ValueError, match="sandbox_homedir"):
        _expand_sandbox_tilde(Path("~/x"), sandbox_homedir=None)


def test_file_mount_parents_includes_files_under_homedir(tmp_path: Path) -> None:
    """File mounts under SANDBOX_HOMEDIR contribute their parent dirs."""
    from eden.providers._impl.container_mounts import _file_mount_parents

    f = tmp_path / "config"
    f.write_text("x")
    mounts = [
        Mount(host=f, sandbox=Path("/home/agent/.config/gh/hosts.yml")),
    ]
    parents = _file_mount_parents(mounts, sandbox_homedir=Path("/home/agent"))
    assert parents == [Path("/home/agent/.config/gh")]


def test_file_mount_parents_skips_directory_mounts(tmp_path: Path) -> None:
    """Directory mounts don't need parent prep — docker handles them."""
    from eden.providers._impl.container_mounts import _file_mount_parents

    d = tmp_path / "dir"
    d.mkdir()
    mounts = [Mount(host=d, sandbox=Path("/home/agent/.npm"))]
    parents = _file_mount_parents(mounts, sandbox_homedir=Path("/home/agent"))
    assert parents == []


def test_file_mount_parents_skips_paths_outside_homedir(tmp_path: Path) -> None:
    """File mounts outside the agent home fail with a clear config error."""
    from eden.providers._impl.container_mounts import _file_mount_parents

    f = tmp_path / "secret"
    f.write_text("x")
    mounts = [Mount(host=f, sandbox=Path("/etc/foo/bar.conf"))]
    with pytest.raises(MountConfigError) as ex:
        _file_mount_parents(mounts, sandbox_homedir=Path("/home/agent"))
    assert "/etc/foo" in str(ex.value)


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

    monkeypatch.setattr("eden.providers._impl.container.subprocess.run", _run)
    extra = (Mount(host=Path("C:/Users/me/cache"), sandbox=Path("cache"), read_only=True),)
    p = make_container_provider(binary=binary, image="alpine", mounts=extra)  # type: ignore[arg-type]
    p.create(opts(tmp_path))

    run_cmd = find_run(captured)
    mount_specs = [run_cmd[i + 1] for i, a in enumerate(run_cmd) if a == "--mount"]
    assert "type=bind,source=C:/Users/me/cache,target=/workspace/cache,readonly" in mount_specs


def test_file_mount_parents_dedupes(tmp_path: Path) -> None:
    """Two file mounts in the same parent only create that parent once."""
    from eden.providers._impl.container_mounts import _file_mount_parents

    a = tmp_path / "a"
    b = tmp_path / "b"
    a.write_text("a")
    b.write_text("b")
    mounts = [
        Mount(host=a, sandbox=Path("/home/agent/.config/x.yml")),
        Mount(host=b, sandbox=Path("/home/agent/.config/y.yml")),
    ]
    parents = _file_mount_parents(mounts, sandbox_homedir=Path("/home/agent"))
    assert parents == [Path("/home/agent/.config")]


def test_file_mount_parents_skips_homedir_itself(tmp_path: Path) -> None:
    """A file mount directly into ``~`` doesn't need parent prep — it IS the homedir."""
    from eden.providers._impl.container_mounts import _file_mount_parents

    f = tmp_path / "a"
    f.write_text("a")
    # Sandbox path /home/agent/foo → parent is /home/agent (the homedir itself).
    mounts = [Mount(host=f, sandbox=Path("/home/agent/.bashrc"))]
    parents = _file_mount_parents(mounts, sandbox_homedir=Path("/home/agent"))
    assert parents == []  # parent equals homedir → skip


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
    # --user 0:0 to act as root
    assert helper[helper.index("--user") + 1] == "0:0"
    # The shell helper script is the 7th positional arg after the container id
    # ('sh', '-c', '<script>', 'sh', <parent>, <uid>, <gid>).
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

    # A kill call was issued to clean up the half-started container.
    kill_calls = [c for c in captured if c[1] == "kill"]
    assert kill_calls, f"expected a kill call to clean up, got: {captured!r}"
