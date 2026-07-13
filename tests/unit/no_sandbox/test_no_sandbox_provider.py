"""Verify no_sandbox provider metadata."""

from __future__ import annotations

import pytest

from eden.providers._types import BranchStrategy
from eden.sandboxes.no_sandbox import provider

pytestmark = pytest.mark.unit


def test_provider_metadata() -> None:
    sandbox_provider = provider()
    assert sandbox_provider.name == "no_sandbox"
    assert sandbox_provider.kind == "bind_mount"
    assert sandbox_provider.supports_strategy(BranchStrategy.head()) is True
    assert sandbox_provider.supports_strategy(BranchStrategy.merge_to_head()) is True
    assert sandbox_provider.supports_strategy(BranchStrategy.named("x")) is True
