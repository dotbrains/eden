"""forkd live-SDK lifecycle integration tests."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from eden.providers._protocols import IsolatedSandboxHandle, SandboxProvider
from tests.integration.forkd.conftest import opts

pytestmark = pytest.mark.integration


def test_finalize_propagates_sandbox_changes(
    forkd_provider_factory: SandboxProvider,
    tmp_path: Path,
) -> None:
    """A fresh microVM + an added file + finalize -> host target sees the file."""
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "preexisting.txt").write_text("base\n")

    target = tmp_path / "target"
    target.mkdir()
    (target / "preexisting.txt").write_text("base\n")

    handle = forkd_provider_factory.create(
        opts(worktree_path=seed, name_hint=f"eden-it-fin-{uuid.uuid4().hex[:6]}")
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
    forkd_provider_factory: SandboxProvider,
    tmp_path: Path,
) -> None:
    """Calling close() twice is safe (matches docker/podman/cloud semantics)."""
    seed = tmp_path / "seed"
    seed.mkdir()
    handle = forkd_provider_factory.create(
        opts(worktree_path=seed, name_hint=f"eden-it-cls-{uuid.uuid4().hex[:6]}")
    )
    handle.close()
    handle.close()
