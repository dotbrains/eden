"""Verify orchestrator branch strategy resolution."""

from __future__ import annotations

import pytest

from eden.errors import InvalidOptions
from eden.orchestrator._setup import resolve_branch_strategy
from eden.providers._types import BranchStrategy
from eden.sandboxes.no_sandbox import provider as no_sandbox_provider

pytestmark = pytest.mark.unit


def test_resolve_branch_strategy_default_for_none_kind() -> None:
    s = resolve_branch_strategy(branch_strategy=None, sandbox_kind="none")
    assert s.tag == "head"


def test_resolve_branch_strategy_default_for_bind_mount() -> None:
    s = resolve_branch_strategy(branch_strategy=None, sandbox_kind="bind_mount")
    assert s.tag == "merge_to_head"


def test_resolve_branch_strategy_explicit_passes_through() -> None:
    s = resolve_branch_strategy(
        branch_strategy=BranchStrategy.named("feat/x"),
        sandbox_kind="bind_mount",
    )
    assert s.tag == "named"
    assert s.branch == "feat/x"


def test_resolve_branch_strategy_base_branch_overrides_default() -> None:
    s = resolve_branch_strategy(
        branch_strategy=None,
        sandbox_kind="bind_mount",
        base_branch="develop",
    )
    assert s.tag == "merge_to_head"
    assert s.base == "develop"


def test_resolve_branch_strategy_base_branch_ignored_for_head_default() -> None:
    s = resolve_branch_strategy(
        branch_strategy=None,
        sandbox_kind="none",
        base_branch="develop",
    )
    assert s.tag == "head"


def test_resolve_branch_strategy_base_branch_conflicts_with_strategy() -> None:
    with pytest.raises(InvalidOptions):
        resolve_branch_strategy(
            branch_strategy=BranchStrategy.named("feat/x"),
            sandbox_kind="bind_mount",
            base_branch="develop",
        )


def test_resolve_branch_strategy_unsupported_raises() -> None:
    p = no_sandbox_provider()
    s = BranchStrategy.head()
    assert p.supports_strategy(s)
