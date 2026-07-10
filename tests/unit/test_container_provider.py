"""Verify make_container_provider create and exec argv shapes."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from eden.providers._impl.container import make_container_provider
from eden.sandboxes.errors import ContainerStartFailed, ImageNotFound, ProviderUnavailable
from tests.unit.container_provider_helpers import find_run, opts

pytestmark = pytest.mark.unit


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
    p.create(opts(tmp_path))

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
    monkeypatch.setattr("eden.providers._impl.container.shutil.which", lambda _b: None)
    p = make_container_provider(binary=binary, image="alpine")  # type: ignore[arg-type]
    with pytest.raises(ProviderUnavailable) as excinfo:
        p.create(opts(tmp_path))
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
        p.create(opts(tmp_path))


@pytest.mark.parametrize("binary", ["docker", "podman"])
def test_image_defaults_from_repo_directory(
    binary: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("eden.providers._impl.container.shutil.which", lambda _b: "/usr/bin/fake")
    captured: list[list[str]] = []
    repo = tmp_path / "My Repo!"
    repo.mkdir()

    def _run(cmd: list[str], *args: object, **kwargs: object) -> MagicMock:
        captured.append(list(cmd))
        m = MagicMock()
        m.returncode = 0
        m.stdout = "container-id\n"
        m.stderr = ""
        return m

    monkeypatch.setattr("eden.providers._impl.container.subprocess.run", _run)
    p = make_container_provider(binary=binary)  # type: ignore[arg-type]
    p.create(opts(repo))

    inspect_cmd = captured[0]
    run_cmd = find_run(captured)
    assert inspect_cmd[:4] == [binary, "image", "inspect", "eden:my-repo"]
    assert "eden:my-repo" in run_cmd


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
        p.create(opts(tmp_path))
    assert excinfo.value.exit_code == 125


@pytest.mark.parametrize("binary", ["docker", "podman"])
def test_container_exec_uses_configured_output_tail(
    binary: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("eden.providers._impl.container.shutil.which", lambda _b: "/usr/bin/fake")
    captured_run: list[list[str]] = []
    captured_stream: list[dict[str, object]] = []

    def _run(cmd: list[str], *args: object, **kwargs: object) -> MagicMock:
        captured_run.append(list(cmd))
        m = MagicMock()
        m.returncode = 0
        m.stdout = "container-id\n"
        m.stderr = ""
        return m

    def _stream_exec(argv: list[str], **kwargs: object) -> object:
        captured_stream.append(kwargs)
        from eden.providers._types import ExecResult

        return ExecResult(stdout="", stderr="", exit_code=0)

    monkeypatch.setattr("eden.providers._impl.container.subprocess.run", _run)
    monkeypatch.setattr("eden.providers._impl.container_handle.stream_exec", _stream_exec)
    p = make_container_provider(
        binary=binary,  # type: ignore[arg-type]
        image="alpine",
        max_output_tail_chars=123,
    )
    handle = p.create(opts(tmp_path))
    handle.exec("echo hi", on_line=lambda _line: None)

    assert captured_stream[0]["max_output_tail_chars"] == 123


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

    class _FakePopen:
        def __init__(self, cmd: list[str]) -> None:
            captured.append(list(cmd))

        def wait(self, timeout: float | None = None) -> int:
            return 0

        def terminate(self) -> None:
            return None

        def kill(self) -> None:
            return None

    monkeypatch.setattr("eden.providers._impl.container.subprocess.Popen", _FakePopen)
    p = make_container_provider(binary=binary, image="alpine")  # type: ignore[arg-type]
    handle = p.create(opts(tmp_path))

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
