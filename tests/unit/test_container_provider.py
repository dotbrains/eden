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
    ImageUidMismatch,
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


def _find_run(captured: list[list[str]]) -> list[str]:
    """Return the first ``<binary> run ...`` command from a captured list.

    Tests use this to be resilient to additional ``image inspect`` pre-flight
    calls inserted before the run.
    """
    for cmd in captured:
        if len(cmd) >= 2 and cmd[1] == "run":
            return cmd
    raise AssertionError(f"no run cmd in captured: {captured!r}")


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
    run_cmd = _find_run(captured)
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
    run_cmd = _find_run(captured)
    assert any(f"{tmp_path}:/workspace:z" in arg for arg in run_cmd)


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
    run_cmd = _find_run(captured)
    # default selinux_label="z" → ":ro,z"
    assert any(f"{tmp_path / 'extra'}:/extra:ro,z" in arg for arg in run_cmd)


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
    run_cmd = _find_run(captured)
    idx = run_cmd.index("--network")
    assert run_cmd[idx + 1] == "host"


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
    p.create(_opts(tmp_path))
    run_cmd = _find_run(captured)
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
    p = make_container_provider(  # type: ignore[arg-type]
        binary=binary,
        image="alpine",
        container_uid=5000,
        container_gid=5001,
    )
    p.create(_opts(tmp_path))
    run_cmd = _find_run(captured)
    idx = run_cmd.index("--user")
    assert run_cmd[idx + 1] == "5000:5001"


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
    p = make_container_provider(  # type: ignore[arg-type]
        binary=binary,
        image="alpine",
        container_uid=1000,
        container_gid=1000,
    )
    with pytest.raises(ImageUidMismatch) as ex:
        p.create(_opts(tmp_path))
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
    p = make_container_provider(  # type: ignore[arg-type]
        binary=binary,
        image="alpine",
        container_uid=1000,
    )
    # Should not raise.
    p.create(_opts(tmp_path))


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
    p.create(_opts(tmp_path))


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
    p = make_container_provider(  # type: ignore[arg-type]
        binary=binary, image="alpine", selinux_label=None
    )
    p.create(_opts(tmp_path))
    run_cmd = _find_run(captured)
    # Workspace mount has no SELinux suffix when disabled.
    assert any(f"{tmp_path}:/workspace" == arg for arg in run_cmd)
    assert not any(arg.endswith(":z") for arg in run_cmd)
    assert not any(arg.endswith(":Z") for arg in run_cmd)


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
    p = make_container_provider(  # type: ignore[arg-type]
        binary=binary, image="alpine", selinux_label="Z"
    )
    p.create(_opts(tmp_path))
    run_cmd = _find_run(captured)
    assert any(arg.endswith(":Z") for arg in run_cmd)


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
    p = make_container_provider(  # type: ignore[arg-type]
        binary=binary, image="alpine", mounts=extra, selinux_label="z"
    )
    p.create(_opts(tmp_path))
    run_cmd = _find_run(captured)
    assert any(f"{tmp_path / 'ro'}:/ro:ro,z" == arg for arg in run_cmd)


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
    p.create(_opts(tmp_path))
    run_cmd = _find_run(captured)
    bind_specs = [run_cmd[i + 1] for i, a in enumerate(run_cmd) if a == "-v"]
    # Expanded to /home/agent/.npm with default selinux label
    assert any(s == f"{tmp_path / 'cache'}:/home/agent/.npm:z" for s in bind_specs), bind_specs


def test_expand_sandbox_tilde_root() -> None:
    from eden.providers._impl.container import _expand_sandbox_tilde

    expanded = _expand_sandbox_tilde(Path("~"), sandbox_homedir=Path("/home/agent"))
    assert expanded == Path("/home/agent")


def test_expand_sandbox_tilde_with_subpath() -> None:
    from eden.providers._impl.container import _expand_sandbox_tilde

    expanded = _expand_sandbox_tilde(
        Path("~/.config/x"), sandbox_homedir=Path("/home/agent")
    )
    assert expanded == Path("/home/agent/.config/x")


def test_expand_sandbox_tilde_passthrough_for_absolute() -> None:
    from eden.providers._impl.container import _expand_sandbox_tilde

    expanded = _expand_sandbox_tilde(
        Path("/etc/hosts"), sandbox_homedir=Path("/home/agent")
    )
    assert expanded == Path("/etc/hosts")


def test_expand_sandbox_tilde_raises_when_homedir_missing() -> None:
    from eden.providers._impl.container import _expand_sandbox_tilde

    with pytest.raises(ValueError, match="sandbox_homedir"):
        _expand_sandbox_tilde(Path("~/x"), sandbox_homedir=None)


@pytest.mark.parametrize("binary", ["docker", "podman"])
def test_interactive_exec_builds_exec_it_argv(
    binary: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``interactive_exec`` wraps argv in ``<binary> exec -it ...``."""
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
    handle = p.create(_opts(tmp_path))

    rc = handle.interactive_exec(  # type: ignore[attr-defined]
        ["claude", "--model", "x"],
        cwd=Path("/workspace"),
        env={"K": "V"},
    )
    assert rc == 0

    # The last captured call is the interactive exec.
    exec_call = captured[-1]
    assert exec_call[:3] == [binary, "exec", "-it"]
    assert "-w" in exec_call
    assert exec_call[exec_call.index("-w") + 1] == "/workspace"
    assert "-e" in exec_call
    assert "K=V" in exec_call
    # Container id appears before the agent argv.
    assert "claude" in exec_call
    assert exec_call.index("claude") > exec_call.index(handle.container_id)  # type: ignore[attr-defined]
