"""Verify FinalizeResult + IsolatedSandboxHandle Protocol shape."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from eden.providers._helpers import make_isolated_provider
from eden.providers._protocols import IsolatedSandboxHandle, SandboxHandle
from eden.providers._types import BranchStrategy, CreateOptions, FinalizeResult

pytestmark = pytest.mark.unit


def test_finalize_result_is_frozen() -> None:
    fr = FinalizeResult(applied=True, files_changed=(Path("a"),), patch_size_bytes=42)
    with pytest.raises(FrozenInstanceError):
        fr.applied = False  # type: ignore[misc]


def test_finalize_result_field_shape() -> None:
    fr = FinalizeResult(
        applied=True,
        files_changed=(Path("src/x.py"), Path("README.md")),
        patch_size_bytes=128,
    )
    assert fr.applied is True
    assert fr.files_changed == (Path("src/x.py"), Path("README.md"))
    assert fr.patch_size_bytes == 128


def test_isolated_sandbox_handle_is_runtime_checkable() -> None:
    """A class with the right shape passes isinstance(x, IsolatedSandboxHandle)."""

    class _Conforming:
        worktree_path = Path("/tmp/x")

        def exec(self, cmd: str, **_kw: object) -> object: ...
        def copy_file_in(self, host: Path, sandbox: Path) -> None: ...
        def copy_file_out(self, sandbox: Path, host: Path) -> None: ...
        def close(self) -> None: ...
        def finalize(self, target: Path) -> FinalizeResult:
            return FinalizeResult(applied=True, files_changed=(), patch_size_bytes=0)

    assert isinstance(_Conforming(), IsolatedSandboxHandle)
    assert isinstance(_Conforming(), SandboxHandle)


def test_sandbox_handle_without_finalize_is_not_isolated() -> None:
    class _BindMount:
        worktree_path = Path("/tmp/x")

        def exec(self, cmd: str, **_kw: object) -> object: ...
        def copy_file_in(self, host: Path, sandbox: Path) -> None: ...
        def copy_file_out(self, sandbox: Path, host: Path) -> None: ...
        def close(self) -> None: ...

    assert isinstance(_BindMount(), SandboxHandle)
    assert not isinstance(_BindMount(), IsolatedSandboxHandle)


def test_make_isolated_provider_returns_isolated_kind() -> None:
    def _create(opts: CreateOptions) -> IsolatedSandboxHandle:
        raise NotImplementedError

    p = make_isolated_provider(name="local", create=_create)
    assert p.name == "local"
    assert p.kind == "isolated"


def test_make_isolated_provider_supports_default_strategies() -> None:
    def _create(opts: CreateOptions) -> IsolatedSandboxHandle:
        raise NotImplementedError

    p = make_isolated_provider(name="local", create=_create)
    assert p.supports_strategy(BranchStrategy.head())
    assert p.supports_strategy(BranchStrategy.merge_to_head())
    assert p.supports_strategy(BranchStrategy.named("x"))


def test_make_isolated_provider_supported_strategies_filter() -> None:
    def _create(opts: CreateOptions) -> IsolatedSandboxHandle:
        raise NotImplementedError

    p = make_isolated_provider(
        name="local",
        create=_create,
        supported_strategies=frozenset({"head"}),
    )
    assert p.supports_strategy(BranchStrategy.head())
    assert not p.supports_strategy(BranchStrategy.merge_to_head())
