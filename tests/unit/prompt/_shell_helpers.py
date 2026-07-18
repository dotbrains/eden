"""Shared helpers for prompt shell-block tests."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path

from eden.providers._types import ExecResult


class FakeHandle:
    worktree_path = Path("/workspace")

    def __init__(self, results: dict[str, ExecResult]) -> None:
        self._results = results
        self.calls: list[str] = []
        self.timeouts: list[float | None] = []

    def exec(
        self,
        cmd: str,
        *,
        on_line: Callable[[str], None] | None = None,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
        stdin: str | None = None,
    ) -> ExecResult:
        self.calls.append(cmd)
        self.timeouts.append(timeout)
        return self._results[cmd]

    def copy_file_in(self, host: Path, sandbox: Path) -> None: ...
    def copy_file_out(self, sandbox: Path, host: Path) -> None: ...
    def close(self) -> None: ...
