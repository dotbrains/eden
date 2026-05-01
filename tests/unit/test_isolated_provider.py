"""Verify the local isolated() provider's lifecycle and finalize behavior."""

from __future__ import annotations

from pathlib import Path

import pytest

from eden.providers._protocols import IsolatedSandboxHandle
from eden.providers._types import BranchStrategy, CreateOptions
from eden.sandboxes.isolated import provider as isolated_provider

pytestmark = pytest.mark.unit


def _opts(host: Path) -> CreateOptions:
    return CreateOptions(
        branch="HEAD",
        worktree_path=host,
        host_repo_path=host,
        env={},
        mounts=(),
        name_hint="test",
    )


def test_provider_kind_and_name() -> None:
    p = isolated_provider()
    assert p.kind == "isolated"
    assert p.name == "isolated"


def test_provider_supports_default_strategies() -> None:
    p = isolated_provider()
    assert p.supports_strategy(BranchStrategy.head())
    assert p.supports_strategy(BranchStrategy.merge_to_head())
    assert p.supports_strategy(BranchStrategy.named("x"))


def test_create_carves_isolated_root_with_copy(tmp_path: Path) -> None:
    host = tmp_path / "host"
    host.mkdir()
    (host / "src.py").write_text("x=1", encoding="utf-8")
    (host / "sub").mkdir()
    (host / "sub" / "y.txt").write_text("y", encoding="utf-8")

    p = isolated_provider()
    handle = p.create(_opts(host))
    try:
        assert handle.worktree_path != host
        assert handle.worktree_path.exists()
        assert (handle.worktree_path / "src.py").read_text() == "x=1"
        assert (handle.worktree_path / "sub" / "y.txt").read_text() == "y"
    finally:
        handle.close()


def test_create_handle_satisfies_isolated_protocol(tmp_path: Path) -> None:
    p = isolated_provider()
    handle = p.create(_opts(tmp_path))
    try:
        assert isinstance(handle, IsolatedSandboxHandle)
    finally:
        handle.close()


def test_close_removes_isolated_root(tmp_path: Path) -> None:
    p = isolated_provider()
    handle = p.create(_opts(tmp_path))
    isolated_root = handle.worktree_path
    assert isolated_root.exists()
    handle.close()
    assert not isolated_root.exists()


def test_close_is_idempotent(tmp_path: Path) -> None:
    p = isolated_provider()
    handle = p.create(_opts(tmp_path))
    handle.close()
    handle.close()  # must not raise


def test_finalize_replays_added_and_changed(tmp_path: Path) -> None:
    host = tmp_path / "host"
    host.mkdir()
    (host / "a.txt").write_text("alpha-orig", encoding="utf-8")
    (host / "b.txt").write_text("beta", encoding="utf-8")

    p = isolated_provider()
    handle = p.create(_opts(host))
    assert isinstance(handle, IsolatedSandboxHandle)
    try:
        # Modify the isolated copy
        (handle.worktree_path / "a.txt").write_text("alpha-new", encoding="utf-8")
        (handle.worktree_path / "c.txt").write_text("gamma", encoding="utf-8")
        (handle.worktree_path / "b.txt").unlink()

        fr = handle.finalize(target=host)
        assert fr.applied is True
        assert (host / "a.txt").read_text() == "alpha-new"
        assert (host / "c.txt").read_text() == "gamma"
        assert not (host / "b.txt").exists()
        assert set(fr.files_changed) == {Path("a.txt"), Path("b.txt"), Path("c.txt")}
    finally:
        handle.close()


def test_default_base_dir_is_under_eden_isolated(tmp_path: Path) -> None:
    host = tmp_path / "host"
    host.mkdir()
    p = isolated_provider()
    handle = p.create(_opts(host))
    try:
        assert (host / ".eden" / "isolated") in handle.worktree_path.parents
    finally:
        handle.close()


def test_explicit_base_dir(tmp_path: Path) -> None:
    host = tmp_path / "host"
    host.mkdir()
    custom = tmp_path / "custom_base"
    p = isolated_provider(base_dir=custom)
    handle = p.create(_opts(host))
    try:
        assert custom in handle.worktree_path.parents
    finally:
        handle.close()
