"""Public surface for sandbox providers and core types."""

from __future__ import annotations

from eden.providers._capabilities import (
    PortSupport,
    ProviderCapabilities,
    capabilities_for,
)
from eden.providers._helpers import make_bind_mount_provider, make_isolated_provider
from eden.providers._protocols import (
    BindMountSandboxHandle,
    IsolatedSandboxHandle,
    SandboxHandle,
    SandboxProcess,
    SandboxProvider,
    SupportsBackgroundExec,
    SupportsPorts,
)
from eden.providers._types import (
    BranchStrategy,
    CreateOptions,
    ExecResult,
    ExposedPort,
    FinalizeResult,
    Mount,
    ProcessStatus,
    StrategyTag,
)

__all__ = [
    "BindMountSandboxHandle",
    "BranchStrategy",
    "CreateOptions",
    "ExecResult",
    "ExposedPort",
    "FinalizeResult",
    "IsolatedSandboxHandle",
    "Mount",
    "PortSupport",
    "ProcessStatus",
    "ProviderCapabilities",
    "SandboxHandle",
    "SandboxProcess",
    "SandboxProvider",
    "StrategyTag",
    "SupportsBackgroundExec",
    "SupportsPorts",
    "capabilities_for",
    "make_bind_mount_provider",
    "make_isolated_provider",
]
