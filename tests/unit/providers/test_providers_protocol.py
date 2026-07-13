"""Verify provider Protocols and runtime_checkable behavior."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path

import pytest

from eden.providers._protocols import (
    BindMountSandboxHandle,
    SandboxHandle,
    SandboxProvider,
)
from eden.providers._types import (
    BranchStrategy,
    CreateOptions,
    ExecResult,
)

pytestmark = pytest.mark.unit


class _GoodHandle:
    worktree_path = Path("/wt")

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
        return ExecResult(stdout="", stderr="", exit_code=0)

    def copy_file_in(self, host: Path, sandbox: Path) -> None:
        return None

    def copy_file_out(self, sandbox: Path, host: Path) -> None:
        return None

    def close(self) -> None:
        return None


class _BadHandleNoExec:
    worktree_path = Path("/wt")


class _GoodProvider:
    name = "fake"
    kind = "bind_mount"

    def supports_strategy(self, strategy: BranchStrategy) -> bool:
        return True

    def create(self, opts: CreateOptions) -> SandboxHandle:
        return _GoodHandle()


def test_good_handle_satisfies_protocol() -> None:
    assert isinstance(_GoodHandle(), SandboxHandle)


def test_bad_handle_rejected() -> None:
    assert not isinstance(_BadHandleNoExec(), SandboxHandle)


def test_bind_mount_handle_subclasses_sandbox_handle() -> None:
    # A BindMountSandboxHandle is just a SandboxHandle with a marker tag.
    assert isinstance(_GoodHandle(), BindMountSandboxHandle)


def test_provider_protocol() -> None:
    p = _GoodProvider()
    assert isinstance(p, SandboxProvider)
    assert p.name == "fake"
    assert p.kind == "bind_mount"
    assert p.supports_strategy(BranchStrategy.head()) is True


def test_public_surface_importable() -> None:
    from eden.providers import (  # noqa: F401
        BindMountSandboxHandle,
        BranchStrategy,
        CreateOptions,
        ExecResult,
        Mount,
        SandboxHandle,
        SandboxProvider,
        StrategyTag,
        make_bind_mount_provider,
    )
