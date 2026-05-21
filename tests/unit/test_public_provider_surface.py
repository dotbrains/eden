"""Test that the public custom-provider surface is importable from the
top-level `eden` package without reaching into `eden.providers._*`.

The shape and naming mirror sandcastle's documented seam — third-party
provider authors should be able to depend on `from eden import ...`
only.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


def test_top_level_factory_imports() -> None:
    from eden import make_bind_mount_provider, make_isolated_provider

    assert make_bind_mount_provider.__name__ == "make_bind_mount_provider"
    assert make_isolated_provider.__name__ == "make_isolated_provider"


def test_top_level_protocol_imports() -> None:
    from eden import (
        BindMountSandboxHandle,
        IsolatedSandboxHandle,
        SandboxHandle,
        SandboxProvider,
    )

    # Just verify they are Protocol classes — they're runtime-checkable.
    assert SandboxHandle is not None
    assert SandboxProvider is not None
    assert BindMountSandboxHandle is not None
    assert IsolatedSandboxHandle is not None


def test_top_level_type_imports() -> None:
    from eden import (
        BranchStrategy,
        CreateOptions,
        FinalizeResult,
        Mount,
    )

    # Sanity-check the dataclasses are constructible and frozen.
    s = BranchStrategy.head()
    assert s.tag == "head"
    fr = FinalizeResult(applied=True, files_changed=(), patch_size_bytes=0)
    assert fr.applied is True
    co = CreateOptions(
        branch="b",
        worktree_path=Path("/wt"),
        host_repo_path=Path("/host"),
        env={},
        mounts=(Mount(host=Path("/h"), sandbox=Path("/s")),),
        name_hint=None,
    )
    assert co.branch == "b"


def test_third_party_provider_only_uses_public_surface() -> None:
    """Smoke-test that a minimal isolated provider can be assembled using
    only top-level `eden` imports.
    """
    from eden import (
        CreateOptions,
        ExecResult,
        FinalizeResult,
        IsolatedSandboxHandle,
        SandboxProvider,
        make_isolated_provider,
    )

    class _Handle:
        worktree_path = Path("/sandbox")

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

        def finalize(self, target: Path) -> FinalizeResult:
            return FinalizeResult(applied=True, files_changed=(), patch_size_bytes=0)

        def close(self) -> None:
            return None

    def _create(_opts: CreateOptions) -> IsolatedSandboxHandle:
        return _Handle()

    p: SandboxProvider = make_isolated_provider(name="example", create=_create)
    assert p.kind == "isolated"
    assert p.name == "example"


def test_eden_providers_package_exports() -> None:
    """The `eden.providers` namespace should expose both factories and
    the full protocol+type surface."""
    import eden.providers as providers

    expected = {
        "BindMountSandboxHandle",
        "BranchStrategy",
        "CreateOptions",
        "ExecResult",
        "FinalizeResult",
        "IsolatedSandboxHandle",
        "Mount",
        "SandboxHandle",
        "SandboxProvider",
        "StrategyTag",
        "make_bind_mount_provider",
        "make_isolated_provider",
    }
    assert expected.issubset(set(providers.__all__))
    for name in expected:
        assert hasattr(providers, name), name
