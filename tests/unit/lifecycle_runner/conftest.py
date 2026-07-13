"""Shared lifecycle hook runner test fakes."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from eden.providers._types import ExecResult


@dataclass
class FakeHandle:
    worktree_path: Path
    seen: list[str]
    fails_for: tuple[str, ...] = ()
    sleep_per_call: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock)

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
        if self.sleep_per_call:
            time.sleep(self.sleep_per_call)
        with self._lock:
            self.seen.append(cmd)
        if cmd in self.fails_for:
            return ExecResult(stdout="", stderr=f"err:{cmd}", exit_code=1)
        return ExecResult(stdout=f"ok:{cmd}\n", stderr="", exit_code=0)

    def copy_file_in(self, host: Path, sandbox: Path) -> None: ...
    def copy_file_out(self, sandbox: Path, host: Path) -> None: ...
    def close(self) -> None: ...
