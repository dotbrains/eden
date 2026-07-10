"""Helpers for docker provider unit tests."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from eden.providers._types import CreateOptions


@dataclass
class Recorded:
    argv: tuple[str, ...]
    stdout: str
    stderr: str
    returncode: int


@dataclass
class SubprocessFake:
    queue: list[tuple[str, str, int]] = field(default_factory=list)
    calls: list[Recorded] = field(default_factory=list)
    which_returns: str | None = "/usr/bin/docker"

    def queue_run(self, stdout: str = "", stderr: str = "", returncode: int = 0) -> None:
        self.queue.append((stdout, stderr, returncode))

    def run(self, argv: list[str], *args: Any, **kwargs: Any) -> Any:
        if not self.queue:
            raise AssertionError(f"unexpected subprocess.run({argv!r})")
        out, err, rc = self.queue.pop(0)
        rec = Recorded(argv=tuple(argv), stdout=out, stderr=err, returncode=rc)
        self.calls.append(rec)
        return subprocess.CompletedProcess(args=argv, returncode=rc, stdout=out, stderr=err)


@pytest.fixture
def fake_subprocess(monkeypatch: pytest.MonkeyPatch) -> SubprocessFake:
    fake = SubprocessFake()
    monkeypatch.setattr(
        "eden.providers._impl.container.shutil.which",
        lambda name: fake.which_returns,
    )
    monkeypatch.setattr("eden.providers._impl.container.subprocess.run", fake.run)
    return fake


def opts(tmp_path: Path) -> CreateOptions:
    return CreateOptions(
        branch="feat/x",
        worktree_path=tmp_path,
        host_repo_path=tmp_path,
        env={"USER_KEY": "u"},
        mounts=(),
        name_hint="hint",
    )
