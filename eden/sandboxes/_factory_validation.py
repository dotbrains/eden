"""Validation helpers for ``create_sandbox``."""

from __future__ import annotations

from eden.errors import InvalidOptions


def raise_copy_to_head_worktree_error(*, branch_strategy: str) -> None:
    raise InvalidOptions(
        code="config.invalid_options",
        message=(
            f"copy_to_worktree= is incompatible with {branch_strategy}; "
            "the worktree IS the host repo, so copying would overwrite it"
        ),
        hint=(
            "drop copy_to_worktree or pick a branch strategy that carves "
            "a separate worktree (merge_to_head or named)"
        ),
    )
