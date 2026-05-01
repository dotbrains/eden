"""Verify the podman provider is a thin shim over make_container_provider."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from eden.providers._types import BranchStrategy
from eden.sandboxes.podman import provider as podman_provider

pytestmark = pytest.mark.unit


def test_podman_provider_returns_bind_mount_kind() -> None:
    p = podman_provider(image="alpine:latest")
    assert p.kind == "bind_mount"
    assert p.name == "podman"


def test_podman_supports_default_strategies() -> None:
    p = podman_provider(image="alpine:latest")
    assert p.supports_strategy(BranchStrategy.head())
    assert p.supports_strategy(BranchStrategy.merge_to_head())
    assert p.supports_strategy(BranchStrategy.named("x"))


def test_podman_uses_podman_binary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Confirm the podman factory threads `binary='podman'` through to subprocess argv."""
    monkeypatch.setattr("eden.providers._impl.container.shutil.which", lambda _b: "/usr/bin/fake")
    captured: list[list[str]] = []

    def _run(cmd: list[str], *args: object, **kwargs: object) -> MagicMock:
        captured.append(list(cmd))
        m = MagicMock()
        m.returncode = 0
        m.stdout = "container-id\n"
        m.stderr = ""
        return m

    monkeypatch.setattr("eden.providers._impl.container.subprocess.run", _run)

    from eden.providers._types import CreateOptions

    opts = CreateOptions(
        branch="HEAD",
        worktree_path=tmp_path,
        host_repo_path=tmp_path,
        env={},
        mounts=(),
        name_hint=None,
    )
    p = podman_provider(image="alpine")
    p.create(opts)

    # First call: podman image inspect ...
    # Second call: podman run -d --rm ...
    assert captured[0][0] == "podman"
    assert captured[1][0] == "podman"
