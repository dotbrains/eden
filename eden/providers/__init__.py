"""Public surface for sandbox providers and core types."""

from __future__ import annotations

from eden.providers._helpers import make_bind_mount_provider, make_isolated_provider
from eden.providers._protocols import (
    BindMountSandboxHandle,
    IsolatedSandboxHandle,
    SandboxHandle,
    SandboxProvider,
)
from eden.providers._types import (
    BranchStrategy,
    CreateOptions,
    ExecResult,
    FinalizeResult,
    Mount,
    StrategyTag,
)

__all__ = [
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
]
