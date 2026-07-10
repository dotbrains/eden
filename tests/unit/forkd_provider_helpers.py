"""Helpers for forkd provider unit tests."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from eden.providers._types import CreateOptions


@dataclass
class FakeResult:
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0


@dataclass
class FakeCommands:
    """Records run() calls and replays canned results in order."""

    results: list[FakeResult]
    calls: list[dict[str, object]] = field(default_factory=list)
    _idx: int = 0

    def run(
        self,
        cmd: str,
        *,
        cwd: str | None = None,
        envs: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> FakeResult:
        self.calls.append({"cmd": cmd, "cwd": cwd, "envs": envs, "timeout": timeout})
        if self._idx < len(self.results):
            result = self.results[self._idx]
            self._idx += 1
            return result
        return FakeResult()


@dataclass
class FakeSandbox:
    commands: FakeCommands
    killed: bool = False

    def kill(self) -> None:
        self.killed = True


def opts(tmp_path: Path) -> CreateOptions:
    return CreateOptions(
        branch="HEAD",
        worktree_path=tmp_path,
        host_repo_path=tmp_path,
        env={},
        mounts=(),
        name_hint="test",
    )


def handle(
    sandbox: FakeSandbox,
    *,
    host: Path,
    env: dict[str, str] | None = None,
    baseline: dict[Path, str] | None = None,
) -> object:
    from eden.sandboxes.forkd import _ForkdHandle

    return _ForkdHandle(
        sandbox=sandbox,  # type: ignore[arg-type]
        worktree_path=Path("/workspace"),
        host_worktree_path=host,
        env=env or {},
        timeout=60.0,
        baseline=baseline or {},
    )
