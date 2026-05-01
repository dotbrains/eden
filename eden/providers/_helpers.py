"""Factory helpers for assembling SandboxProvider instances."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from eden.providers._protocols import (
    BindMountSandboxHandle,
    SandboxHandle,
    SandboxProvider,
)
from eden.providers._types import BranchStrategy, CreateOptions, StrategyTag


@dataclass
class _BindMountProvider:
    name: str
    kind: Literal["bind_mount", "isolated", "none"]
    _create_fn: Callable[[CreateOptions], BindMountSandboxHandle]
    _supported: frozenset[StrategyTag]

    def supports_strategy(self, strategy: BranchStrategy) -> bool:
        return strategy.tag in self._supported

    def create(self, opts: CreateOptions) -> SandboxHandle:
        return self._create_fn(opts)


_DEFAULT_STRATEGIES: frozenset[StrategyTag] = frozenset({"head", "merge_to_head", "named"})


def make_bind_mount_provider(
    name: str,
    create: Callable[[CreateOptions], BindMountSandboxHandle],
    *,
    supported_strategies: frozenset[StrategyTag] = _DEFAULT_STRATEGIES,
) -> SandboxProvider:
    """Wrap a `create` function into a `SandboxProvider` with kind=bind_mount."""
    return _BindMountProvider(
        name=name,
        kind="bind_mount",
        _create_fn=create,
        _supported=supported_strategies,
    )
