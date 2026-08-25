"""Verify Vercel provider finalize behavior."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from eden.providers._impl.http_rest import RestClient
from tests.unit.vercel_provider_helpers import mock_client

pytestmark = pytest.mark.unit


def test_finalize_no_changes_returns_applied_true(tmp_path: Path) -> None:
    from eden.sandboxes.vercel import _VercelHandle

    client = mock_client({"stdout": "", "stderr": "", "exitCode": 0})
    handle = _VercelHandle(
        client=client,
        session_id="sess-1",
        name="sb-1",
        worktree_path=Path("/workspace"),
        host_worktree_path=tmp_path,
        baseline={},
        team_id=None,
    )
    fr = handle.finalize(target=tmp_path)
    assert fr.applied is True
    assert fr.files_changed == ()
    assert fr.patch_size_bytes == 0


def test_finalize_pulls_added_files_to_target(tmp_path: Path) -> None:
    from eden.sandboxes.vercel import _VercelHandle

    target = tmp_path / "target"
    target.mkdir()

    base64_payload = "aGVsbG8="
    client = MagicMock(spec=RestClient)
    client.post.side_effect = [
        {"stdout": "abc123  ./new.txt\n", "stderr": "", "exitCode": 0},
        {"stdout": base64_payload, "stderr": "", "exitCode": 0},
    ]
    handle = _VercelHandle(
        client=client,
        session_id="sess-1",
        name="sb-1",
        worktree_path=Path("/workspace"),
        host_worktree_path=target,
        baseline={},
        team_id=None,
    )
    fr = handle.finalize(target=target)
    assert fr.applied is True
    assert (target / "new.txt").read_bytes() == b"hello"
    assert Path("new.txt") in fr.files_changed


def test_finalize_propagates_deletes(tmp_path: Path) -> None:
    from eden.sandboxes.vercel import _VercelHandle

    target = tmp_path / "target"
    target.mkdir()
    (target / "to_delete.txt").write_text("gone soon", encoding="utf-8")

    client = mock_client({"stdout": "", "stderr": "", "exitCode": 0})
    handle = _VercelHandle(
        client=client,
        session_id="sess-1",
        name="sb-1",
        worktree_path=Path("/workspace"),
        host_worktree_path=target,
        baseline={Path("to_delete.txt"): "old-hash"},
        team_id=None,
    )
    fr = handle.finalize(target=target)
    assert fr.applied is True
    assert not (target / "to_delete.txt").exists()


def test_finalize_returns_not_applied_on_snapshot_failure(tmp_path: Path) -> None:
    from eden.sandboxes.vercel import _VercelHandle

    client = MagicMock(spec=RestClient)
    client.post.side_effect = RuntimeError("network down")
    handle = _VercelHandle(
        client=client,
        session_id="sess-1",
        name="sb-1",
        worktree_path=Path("/workspace"),
        host_worktree_path=tmp_path,
        baseline={},
        team_id=None,
    )
    fr = handle.finalize(target=tmp_path)
    assert fr.applied is False
