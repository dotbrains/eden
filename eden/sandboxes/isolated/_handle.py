"""Handle implementation for the local isolated sandbox provider."""

from __future__ import annotations

import shutil
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from eden.providers._impl import patch_sync
from eden.providers._process_local import start_local_process
from eden.providers._types import ExecResult, ExposedPort, FinalizeResult
from eden.sandboxes._exec import stream_exec


@dataclass
class IsolatedHandle:
    worktree_path: Path
    host_worktree_path: Path
    baseline: dict[Path, str]
    _preserved: bool = False

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
        merged_cwd = cwd if cwd is not None else self.worktree_path
        return stream_exec(
            ["/bin/sh", "-c", cmd],
            cmd_for_error=cmd,
            shell=False,
            cwd=merged_cwd,
            env=env,
            on_line=on_line,
            timeout=timeout,
            stdin=stdin,
        )

    def start(
        self,
        cmd: str,
        *,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
    ) -> object:
        merged_cwd = cwd if cwd is not None else self.worktree_path
        return start_local_process(
            ["/bin/sh", "-c", cmd],
            cmd_for_error=cmd,
            shell=False,
            cwd=merged_cwd,
            env=env,
        )

    def expose_port(self, port: int, *, public: bool = False) -> ExposedPort:
        return ExposedPort(port=port, url=f"http://localhost:{port}", public=public)

    def copy_file_in(self, host: Path, sandbox: Path) -> None:
        sandbox.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(host, sandbox)

    def copy_file_out(self, sandbox: Path, host: Path) -> None:
        host.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(sandbox, host)

    def finalize(self, target: Path) -> FinalizeResult:
        after = patch_sync.snapshot(self.worktree_path)
        d = patch_sync.diff(before=self.baseline, after=after)
        return patch_sync.apply(d, src=self.worktree_path, dst=target)

    def preserve(self) -> None:
        """Keep the isolated copy on disk after ``close()``."""
        self._preserved = True

    def close(self) -> None:
        if self._preserved:
            return
        if self.worktree_path.exists():
            shutil.rmtree(self.worktree_path, ignore_errors=True)


__all__ = ["IsolatedHandle"]
