"""Verify no_sandbox copy and close behavior."""

from __future__ import annotations

from pathlib import Path

import pytest

from eden.sandboxes.no_sandbox import provider
from tests.unit.no_sandbox.conftest import opts

pytestmark = pytest.mark.unit


def test_handle_copy_in_and_out(tmp_path: Path) -> None:
    src = tmp_path / "a.txt"
    src.write_text("body")
    dst = tmp_path / "b.txt"
    handle = provider().create(opts(tmp_path))
    try:
        handle.copy_file_in(src, dst)
        assert dst.read_text() == "body"
        out = tmp_path / "c.txt"
        handle.copy_file_out(dst, out)
        assert out.read_text() == "body"
    finally:
        handle.close()


def test_handle_close_is_noop(tmp_path: Path) -> None:
    handle = provider().create(opts(tmp_path))
    handle.close()
    handle.close()
