"""Verify ``upload_dir_via_tar`` packs a directory into a single exec call."""

from __future__ import annotations

import base64
import io
import tarfile
from collections.abc import Callable, Mapping
from pathlib import Path

import pytest

from eden.providers._impl.dir_upload import upload_dir_via_tar
from eden.providers._types import ExecResult

pytestmark = pytest.mark.unit


def test_upload_dir_via_tar_packs_directory(tmp_path: Path) -> None:
    src = tmp_path / "src"
    (src / "sub").mkdir(parents=True)
    (src / "a.txt").write_text("alpha")
    (src / "sub" / "b.txt").write_text("beta")

    received: list[str] = []

    def fake_exec(
        cmd: str,
        *,
        on_line: Callable[[str], None] | None = None,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> ExecResult:
        received.append(cmd)
        return ExecResult(stdout="", stderr="", exit_code=0)

    result = upload_dir_via_tar(fake_exec, host=src, sandbox=Path("/workspace/out"))
    assert result.exit_code == 0
    assert len(received) == 1
    cmd = received[0]
    assert cmd.startswith("mkdir -p /workspace/out && ")
    assert "tar -xzf - -C /workspace/out" in cmd

    # Extract the embedded base64 and verify the tar round-trips both files.
    b64 = cmd.split("echo ", 1)[1].split(" | ", 1)[0]
    raw = base64.b64decode(b64)
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tar:
        names = sorted(m.name.lstrip("./") for m in tar.getmembers() if m.isfile())
    assert names == ["a.txt", "sub/b.txt"]
