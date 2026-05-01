"""Verify docker cp wiring (copy_file_in / copy_file_out)."""

from __future__ import annotations

from pathlib import Path

import pytest

from eden.providers._types import CreateOptions
from eden.sandboxes.docker import provider

pytestmark = pytest.mark.integration


def test_copy_in_and_out_round_trip(eden_test_image: str, tmp_path: Path) -> None:
    p = provider(image=eden_test_image)
    handle = p.create(
        CreateOptions(
            branch="main",
            worktree_path=tmp_path,
            host_repo_path=tmp_path,
            env={},
            mounts=(),
            name_hint="copy",
        )
    )
    try:
        src = tmp_path / "in.txt"
        src.write_text("hello in")
        handle.copy_file_in(src, Path("/tmp/in.txt"))
        result = handle.exec("cat /tmp/in.txt")
        assert "hello in" in result.stdout

        handle.exec("echo 'hello out' > /tmp/out.txt")
        dest = tmp_path / "out.txt"
        handle.copy_file_out(Path("/tmp/out.txt"), dest)
        assert "hello out" in dest.read_text()
    finally:
        handle.close()
