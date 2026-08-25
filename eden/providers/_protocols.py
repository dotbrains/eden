"""Runtime-checkable Protocols for sandbox providers and handles."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from typing import Literal, Protocol, runtime_checkable

from eden.providers._types import (
    BranchStrategy,
    CreateOptions,
    ExecResult,
    ExposedPort,
    FinalizeResult,
    ProcessStatus,
)


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
        stdin: str | None = None,
    ) -> ExecResult:
        """Run ``cmd`` in the sandbox and return its captured result.

        ``stdin``, when given, is written to the command's stdin. Providers
        that talk to the host or to a container runtime pipe it directly;
        cloud / REST providers (daytona, vercel) wrap the command in
        ``echo <base64> | base64 -d | (cmd)`` so the payload survives the
        REST round-trip. Useful for delivering large agent prompts that
        exceed the 128 KB Linux execve argv limit.
        """
        ...

    def copy_file_in(self, host: Path, sandbox: Path) -> None: ...

    def copy_file_out(self, sandbox: Path, host: Path) -> None: ...

    def close(self) -> None: ...


@runtime_checkable
class SupportsPorts(SandboxHandle, Protocol):
    """Optional. Detected via ``hasattr(handle, "expose_port")``."""

    def expose_port(self, port: int, *, public: bool = False) -> ExposedPort: ...


@runtime_checkable
class SandboxProcess(Protocol):
    def status(self) -> ProcessStatus: ...

    def output(self) -> Iterator[str]: ...

    def write(self, data: str) -> None: ...

    def wait(self, *, timeout: float | None = None) -> ExecResult: ...

    def kill(self) -> None: ...


@runtime_checkable
class SupportsBackgroundExec(SandboxHandle, Protocol):
    """Optional. Detected via ``hasattr(handle, "start")``."""

    def start(
        self,
        cmd: str,
        *,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
    ) -> SandboxProcess: ...


@runtime_checkable
class BindMountSandboxHandle(SandboxHandle, Protocol):
    """Marker — bind-mount providers don't add methods, but the type tag
    distinguishes them from isolated handles for orchestrator narrowing."""


@runtime_checkable
class IsolatedSandboxHandle(SandboxHandle, Protocol):
    """A SandboxHandle whose state is replicated to the host on close via
    a `finalize(target)` call. Cloud and local "isolated" providers implement
    this; bind-mount providers (docker, podman, no_sandbox) do not.

    The orchestrator detects this Protocol via ``hasattr(handle, "finalize")``;
    the runtime-checkable Protocol exists for type-checker narrowing.
    """

    def finalize(self, target: Path) -> FinalizeResult: ...


@runtime_checkable
class SandboxProvider(Protocol):
    name: str
    kind: Literal["bind_mount", "isolated", "none"]

    def supports_strategy(self, strategy: BranchStrategy) -> bool: ...

    def create(self, opts: CreateOptions) -> SandboxHandle: ...
