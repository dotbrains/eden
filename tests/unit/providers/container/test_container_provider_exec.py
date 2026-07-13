"""Verify container provider exec argv shapes."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from eden.providers._impl.container import make_container_provider
from tests.unit.providers.container.container_provider_helpers import opts

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("binary", ["docker", "podman"])
def test_container_exec_uses_configured_output_tail(
    binary: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "eden.providers._impl.container.shutil.which",
        lambda _binary: "/usr/bin/fake",
    )
    captured_stream: list[dict[str, object]] = []

    def _run(cmd: list[str], *args: object, **kwargs: object) -> MagicMock:
        result = MagicMock()
        result.returncode = 0
        result.stdout = "container-id\n"
        result.stderr = ""
        return result

    def _stream_exec(argv: list[str], **kwargs: object) -> object:
        captured_stream.append(kwargs)
        from eden.providers._types import ExecResult

        return ExecResult(stdout="", stderr="", exit_code=0)

    monkeypatch.setattr("eden.providers._impl.container.subprocess.run", _run)
    monkeypatch.setattr("eden.providers._impl.container_handle.stream_exec", _stream_exec)
    provider = make_container_provider(
        binary=binary,  # type: ignore[arg-type]
        image="alpine",
        max_output_tail_chars=123,
    )
    handle = provider.create(opts(tmp_path))
    handle.exec("echo hi", on_line=lambda _line: None)

    assert captured_stream[0]["max_output_tail_chars"] == 123


@pytest.mark.parametrize("binary", ["docker", "podman"])
def test_interactive_exec_builds_exec_it_argv(
    binary: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``interactive_exec`` wraps argv in ``<binary> exec -it ...``."""
    monkeypatch.setattr(
        "eden.providers._impl.container.shutil.which",
        lambda _binary: "/usr/bin/fake",
    )
    captured: list[list[str]] = []

    def _run(cmd: list[str], *args: object, **kwargs: object) -> MagicMock:
        captured.append(list(cmd))
        result = MagicMock()
        result.returncode = 0
        result.stdout = "container-id\n"
        return result

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
    provider = make_container_provider(binary=binary, image="alpine")  # type: ignore[arg-type]
    handle = provider.create(opts(tmp_path))

    rc = handle.interactive_exec(  # type: ignore[attr-defined]
        ["claude", "--model", "x"],
        cwd=Path("/workspace"),
        env={"K": "V"},
    )
    assert rc == 0

    exec_call = captured[-1]
    assert exec_call[:3] == [binary, "exec", "-it"]
    assert "-w" in exec_call
    assert exec_call[exec_call.index("-w") + 1] == "/workspace"
    assert "-e" in exec_call
    assert "K=V" in exec_call
    assert "claude" in exec_call
    assert exec_call.index("claude") > exec_call.index(handle.container_id)  # type: ignore[attr-defined]
