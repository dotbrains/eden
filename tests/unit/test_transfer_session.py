"""Verify the public transfer_session helper."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eden.errors import SessionCaptureFailed
from eden.session import transfer_session

pytestmark = pytest.mark.unit


def test_transfers_jsonl_with_cwd_rewrite(tmp_path: Path) -> None:
    src = tmp_path / "src.jsonl"
    src.write_text(
        json.dumps({"cwd": "/host-a/repo", "msg": "x"}) + "\n",
        encoding="utf-8",
    )
    dest = tmp_path / "out" / "dest.jsonl"  # parent doesn't exist yet
    result = transfer_session(
        source=src,
        dest=dest,
        source_cwd="/host-a/repo",
        dest_cwd="/host-b/repo",
    )
    assert result == dest
    body = dest.read_text(encoding="utf-8")
    assert "/host-b/repo" in body
    assert "/host-a/repo" not in body


def test_preserves_lines_that_do_not_match_source_cwd(tmp_path: Path) -> None:
    src = tmp_path / "src.jsonl"
    src.write_text(
        json.dumps({"cwd": "/somewhere/else", "msg": "unchanged"}) + "\n",
        encoding="utf-8",
    )
    dest = tmp_path / "dest.jsonl"
    transfer_session(
        source=src,
        dest=dest,
        source_cwd="/host-a/repo",
        dest_cwd="/host-b/repo",
    )
    assert "/somewhere/else" in dest.read_text(encoding="utf-8")


def test_missing_source_raises(tmp_path: Path) -> None:
    with pytest.raises(SessionCaptureFailed):
        transfer_session(
            source=tmp_path / "nope.jsonl",
            dest=tmp_path / "dest.jsonl",
            source_cwd="/a",
            dest_cwd="/b",
        )
