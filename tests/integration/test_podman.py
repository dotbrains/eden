"""Integration tests for the podman provider.

Linux-only; gated on `shutil.which("podman")`. Mirrors the docker integration
tests' shape so podman behavior parity is verifiable.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from eden.providers._types import CreateOptions
from eden.sandboxes.podman import provider as podman_provider

pytestmark = pytest.mark.integration


def _require_podman() -> None:
    if shutil.which("podman") is None:
        pytest.skip("podman not installed")


def _opts(tmp_path: Path) -> CreateOptions:
    return CreateOptions(
        branch="HEAD",
        worktree_path=tmp_path,
        host_repo_path=tmp_path,
        env={},
        mounts=(),
        name_hint="eden-podman-test",
    )


def test_create_and_close(tmp_path: Path) -> None:
    _require_podman()
    p = podman_provider(image="docker.io/library/alpine:3")
    handle = p.create(_opts(tmp_path))
    try:
        assert handle.worktree_path == Path("/workspace")
    finally:
        handle.close()


def test_exec_returns_stdout(tmp_path: Path) -> None:
    _require_podman()
    p = podman_provider(image="docker.io/library/alpine:3")
    handle = p.create(_opts(tmp_path))
    try:
        result = handle.exec("echo hello")
        assert result.exit_code == 0
        assert "hello" in result.stdout
    finally:
        handle.close()


def test_copy_file_in_then_exec(tmp_path: Path) -> None:
    _require_podman()
    src = tmp_path / "payload.txt"
    src.write_text("FROM HOST", encoding="utf-8")
    p = podman_provider(image="docker.io/library/alpine:3")
    handle = p.create(_opts(tmp_path))
    try:
        handle.copy_file_in(src, Path("/tmp/payload.txt"))
        result = handle.exec("cat /tmp/payload.txt")
        assert result.exit_code == 0
        assert "FROM HOST" in result.stdout
    finally:
        handle.close()


def test_close_is_idempotent(tmp_path: Path) -> None:
    _require_podman()
    p = podman_provider(image="docker.io/library/alpine:3")
    handle = p.create(_opts(tmp_path))
    handle.close()
    handle.close()  # must not raise
