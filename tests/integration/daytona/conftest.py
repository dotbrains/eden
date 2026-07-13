"""Shared Daytona integration fixtures."""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from eden.providers._protocols import IsolatedSandboxHandle, SandboxProvider
from eden.providers._types import CreateOptions
from eden.sandboxes.daytona import provider as daytona_provider


def _require_credentials() -> str:
    """Return the api key from the env, or skip the test cleanly."""
    key = os.environ.get("DAYTONA_API_KEY")
    if not key:
        pytest.skip("DAYTONA_API_KEY not set; skipping Daytona integration tests")
    return key


def _opts(*, worktree_path: Path, name_hint: str) -> CreateOptions:
    return CreateOptions(
        branch="HEAD",
        worktree_path=worktree_path,
        host_repo_path=worktree_path,
        env={},
        mounts=(),
        name_hint=name_hint,
    )


@pytest.fixture(scope="session")
def daytona_provider_factory() -> SandboxProvider:
    _require_credentials()
    return daytona_provider()


@pytest.fixture
def daytona_options() -> Callable[[Path, str], CreateOptions]:
    def _create(worktree_path: Path, name_hint: str) -> CreateOptions:
        return _opts(worktree_path=worktree_path, name_hint=name_hint)

    return _create


@pytest.fixture(scope="session")
def daytona_handle(
    daytona_provider_factory: SandboxProvider,
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[IsolatedSandboxHandle]:
    """Single sandbox shared across the read/exec/copy tests.

    Each spin-up costs real Daytona time. Tests that depend on this
    fixture must namespace any files they write under ``/workspace`` to
    avoid bleeding state into one another.
    """
    seed_dir = tmp_path_factory.mktemp("daytona-seed")
    (seed_dir / "seed.txt").write_text("hello from host\n")
    name_hint = f"eden-it-{uuid.uuid4().hex[:8]}"
    handle = daytona_provider_factory.create(_opts(worktree_path=seed_dir, name_hint=name_hint))
    assert isinstance(handle, IsolatedSandboxHandle)
    try:
        yield handle
    finally:
        handle.close()
