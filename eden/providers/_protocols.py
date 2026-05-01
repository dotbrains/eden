"""Runtime-checkable Protocols for sandbox providers and handles."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Literal, Protocol, runtime_checkable

from eden.providers._types import BranchStrategy, CreateOptions, ExecResult


@runtime_checkable
class SandboxHandle(Protocol):
    worktree_path: Path

    def exec(
        self,
        cmd: str,
        *,
        on_line: Callable[[str], None] | None = None,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> ExecResult: ...

    def copy_file_in(self, host: Path, sandbox: Path) -> None: ...

    def copy_file_out(self, sandbox: Path, host: Path) -> None: ...

    def close(self) -> None: ...


@runtime_checkable
class BindMountSandboxHandle(SandboxHandle, Protocol):
    """Marker — bind-mount providers don't add methods, but the type tag
    distinguishes them from isolated handles for orchestrator narrowing."""


@runtime_checkable
class SandboxProvider(Protocol):
    name: str
    kind: Literal["bind_mount", "isolated", "none"]

    def supports_strategy(self, strategy: BranchStrategy) -> bool: ...

    def create(self, opts: CreateOptions) -> SandboxHandle: ...
