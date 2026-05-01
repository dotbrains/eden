"""Verify make_bind_mount_provider produces a valid SandboxProvider."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path

import pytest

from eden.providers._helpers import make_bind_mount_provider
from eden.providers._protocols import (
    BindMountSandboxHandle,
    SandboxProvider,
)
from eden.providers._types import (
    BranchStrategy,
    CreateOptions,
    ExecResult,
)

pytestmark = pytest.mark.unit


class _StubHandle:
    worktree_path = Path("/wt")

    def exec(
        self,
        cmd: str,
        *,
        on_line: Callable[[str], None] | None = None,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> ExecResult:
        return ExecResult(stdout="", stderr="", exit_code=0)

    def copy_file_in(self, host: Path, sandbox: Path) -> None:
        return None

    def copy_file_out(self, sandbox: Path, host: Path) -> None:
        return None

    def close(self) -> None:
        return None


def _make_create() -> Callable[[CreateOptions], BindMountSandboxHandle]:
    return lambda opts: _StubHandle()


def test_make_bind_mount_provider_basic() -> None:
    p = make_bind_mount_provider("stub", _make_create())
    assert isinstance(p, SandboxProvider)
    assert p.name == "stub"
    assert p.kind == "bind_mount"


def test_default_supports_all_three_strategies() -> None:
    p = make_bind_mount_provider("stub", _make_create())
    assert p.supports_strategy(BranchStrategy.head()) is True
    assert p.supports_strategy(BranchStrategy.merge_to_head()) is True
    assert p.supports_strategy(BranchStrategy.named("x")) is True


def test_restricted_strategies() -> None:
    p = make_bind_mount_provider(
        "stub",
        _make_create(),
        supported_strategies=frozenset({"merge_to_head"}),
    )
    assert p.supports_strategy(BranchStrategy.head()) is False
    assert p.supports_strategy(BranchStrategy.merge_to_head()) is True
    assert p.supports_strategy(BranchStrategy.named("x")) is False


def test_create_invokes_callable() -> None:
    seen: list[CreateOptions] = []

    def create(opts: CreateOptions) -> BindMountSandboxHandle:
        seen.append(opts)
        return _StubHandle()

    p = make_bind_mount_provider("stub", create)
    opts = CreateOptions(
        branch="main",
        worktree_path=Path("/wt"),
        host_repo_path=Path("/host"),
        env={},
        mounts=(),
        name_hint=None,
    )
    h = p.create(opts)
    assert seen == [opts]
    assert h.worktree_path == Path("/wt")
