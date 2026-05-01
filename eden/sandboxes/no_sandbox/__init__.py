"""no_sandbox: run commands directly on the host via subprocess+shell."""

from __future__ import annotations

import shutil
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from eden.providers._helpers import make_bind_mount_provider
from eden.providers._protocols import (
    BindMountSandboxHandle,
    SandboxProvider,
)
from eden.providers._types import CreateOptions, ExecResult
from eden.sandboxes._exec import stream_exec


@dataclass
class _NoSandboxHandle:
    worktree_path: Path

    def exec(
        self,
        cmd: str,
        *,
        on_line: Callable[[str], None] | None = None,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> ExecResult:
        return stream_exec(
            cmd,
            cmd_for_error=cmd,
            shell=True,
            cwd=cwd or self.worktree_path,
            env=env,
            on_line=on_line,
            timeout=timeout,
        )

    def copy_file_in(self, host: Path, sandbox: Path) -> None:
        shutil.copy2(host, sandbox)

    def copy_file_out(self, sandbox: Path, host: Path) -> None:
        shutil.copy2(sandbox, host)

    def close(self) -> None:
        return None


def _create_no_sandbox(opts: CreateOptions) -> BindMountSandboxHandle:
    return _NoSandboxHandle(worktree_path=opts.worktree_path)


def provider() -> SandboxProvider:
    return make_bind_mount_provider(
        name="no_sandbox",
        create=_create_no_sandbox,
        supported_strategies=frozenset({"head", "merge_to_head", "named"}),
    )


__all__ = ["provider"]
