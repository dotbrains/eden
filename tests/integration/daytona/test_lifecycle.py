"""Daytona sandbox lifecycle integration tests."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from pathlib import Path

import pytest

from eden.providers._protocols import IsolatedSandboxHandle, SandboxProvider
from eden.providers._types import CreateOptions

pytestmark = pytest.mark.integration


def test_finalize_propagates_sandbox_changes(
    daytona_provider_factory: SandboxProvider,
    daytona_options: Callable[[Path, str], CreateOptions],
    tmp_path: Path,
) -> None:
    """A fresh sandbox + an added file + finalize → host target sees the file.

    Uses its own sandbox (not the session-scoped one) so the baseline
    snapshot is clean and the diff is unambiguous.
    """
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "preexisting.txt").write_text("base\n")

    target = tmp_path / "target"
    target.mkdir()
    # Pre-seed target with the same baseline so finalize's diff has a
    # clean before/after surface to compare against.
    (target / "preexisting.txt").write_text("base\n")

    handle = daytona_provider_factory.create(
        daytona_options(seed, f"eden-it-fin-{uuid.uuid4().hex[:6]}")
    )
    assert isinstance(handle, IsolatedSandboxHandle)
    try:
        write = handle.exec("printf 'added via sandbox' > /workspace/new.txt")
        assert write.exit_code == 0, write.stderr

        result = handle.finalize(target)
        assert result.applied is True
        assert Path("new.txt") in result.files_changed
    finally:
        handle.close()

    landed = target / "new.txt"
    assert landed.read_text() == "added via sandbox"


def test_close_is_idempotent(
    daytona_provider_factory: SandboxProvider,
    daytona_options: Callable[[Path, str], CreateOptions],
    tmp_path: Path,
) -> None:
    """Calling close() twice is safe (matches docker/podman semantics)."""
    seed = tmp_path / "seed"
    seed.mkdir()
    handle = daytona_provider_factory.create(
        daytona_options(seed, f"eden-it-cls-{uuid.uuid4().hex[:6]}")
    )
    handle.close()
    # Second close should silently no-op (RestNotFoundError swallowed).
    handle.close()
