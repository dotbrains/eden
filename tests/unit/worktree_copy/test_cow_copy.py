"""Verify accelerated path copy falls back safely."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from eden.orchestrator.copying._cow import copy_path

pytestmark = pytest.mark.unit


def test_copy_path_uses_reflink_cp_for_new_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = tmp_path / "src.txt"
    dst = tmp_path / "dst.txt"
    src.write_text("payload")
    calls: list[list[str]] = []

    def _run(argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        dst.write_text(src.read_text())
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr("eden.orchestrator.copying._cow.sys.platform", "linux")
    monkeypatch.setattr("eden.orchestrator.copying._cow.subprocess.run", _run)

    copy_path(src, dst)

    assert calls == [["cp", "-R", "--reflink=auto", str(src), str(dst)]]
    assert dst.read_text() == "payload"


def test_copy_path_falls_back_when_cow_cp_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = tmp_path / "src.txt"
    dst = tmp_path / "dst.txt"
    src.write_text("payload")

    def _run(argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(1, argv, stderr="unsupported")

    monkeypatch.setattr("eden.orchestrator.copying._cow.subprocess.run", _run)

    copy_path(src, dst)

    assert dst.read_text() == "payload"
