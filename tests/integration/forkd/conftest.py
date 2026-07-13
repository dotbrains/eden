"""Shared forkd integration fixtures."""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest

from eden.providers._protocols import IsolatedSandboxHandle, SandboxProvider
from eden.providers._types import CreateOptions
from eden.sandboxes.forkd import provider as forkd_provider


def require_forkd() -> str:
    """Return the snapshot tag from the env, or skip the test cleanly."""
    try:
        import forkd  # type: ignore[import-not-found]  # noqa: F401
    except ImportError:
        pytest.skip("forkd SDK not importable; skipping forkd integration tests")
    snapshot = os.environ.get("FORKD_SNAPSHOT")
    if not snapshot:
        pytest.skip("FORKD_SNAPSHOT not set; skipping forkd integration tests")
    return snapshot


@pytest.fixture(scope="session")
def forkd_provider_factory() -> SandboxProvider:
    snapshot = require_forkd()
    return forkd_provider(snapshot=snapshot)


def opts(*, worktree_path: Path, name_hint: str) -> CreateOptions:
    return CreateOptions(
        branch="HEAD",
        worktree_path=worktree_path,
        host_repo_path=worktree_path,
        env={},
        mounts=(),
        name_hint=name_hint,
    )


@pytest.fixture(scope="session")
def forkd_handle(
    forkd_provider_factory: SandboxProvider,
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[IsolatedSandboxHandle]:
    """Single microVM shared across read/exec/copy tests."""
    seed_dir = tmp_path_factory.mktemp("forkd-seed")
    (seed_dir / "seed.txt").write_text("hello from host\n")
    name_hint = f"eden-it-{uuid.uuid4().hex[:8]}"
    handle = forkd_provider_factory.create(opts(worktree_path=seed_dir, name_hint=name_hint))
    assert isinstance(handle, IsolatedSandboxHandle)
    try:
        yield handle
    finally:
        handle.close()
