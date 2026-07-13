"""Verify Daytona provider finalize behavior."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from eden.providers._impl.http_rest import RestClient
from tests.unit.daytona_provider_helpers import mock_client

pytestmark = pytest.mark.unit


def test_finalize_no_changes_returns_applied_true(tmp_path: Path) -> None:
    """When sandbox snapshot equals baseline, finalize is a no-op success."""
    from eden.sandboxes.daytona import _DaytonaHandle

    # The shell command in _snapshot_remote returns empty stdout when no files.
    client = mock_client({"stdout": "", "stderr": "", "exit_code": 0})
    handle = _DaytonaHandle(
        client=client,
        sandbox_id="sb-1",
        worktree_path=Path("/workspace"),
        host_worktree_path=tmp_path,
        baseline={},
    )
    fr = handle.finalize(target=tmp_path)
    assert fr.applied is True
    assert fr.files_changed == ()
    assert fr.patch_size_bytes == 0


def test_finalize_pulls_added_files_to_target(tmp_path: Path) -> None:
    """Sandbox has a file not in baseline - finalize REST-pulls it to target."""
    from eden.sandboxes.daytona import _DaytonaHandle

    target = tmp_path / "target"
    target.mkdir()

    base64_payload = "aGVsbG8="  # "hello"
    client = MagicMock(spec=RestClient)
    client.post.side_effect = [
        {"stdout": "abc123  ./new.txt\n", "stderr": "", "exit_code": 0},
        {"stdout": base64_payload, "stderr": "", "exit_code": 0},
    ]
    handle = _DaytonaHandle(
        client=client,
        sandbox_id="sb-1",
        worktree_path=Path("/workspace"),
        host_worktree_path=target,
        baseline={},
    )
    fr = handle.finalize(target=target)
    assert fr.applied is True
    assert (target / "new.txt").read_bytes() == b"hello"
    assert Path("new.txt") in fr.files_changed


def test_finalize_propagates_deletes(tmp_path: Path) -> None:
    """Baseline has a file; sandbox snapshot doesn't - finalize removes it from target."""
    from eden.sandboxes.daytona import _DaytonaHandle

    target = tmp_path / "target"
    target.mkdir()
    (target / "to_delete.txt").write_text("gone soon", encoding="utf-8")

    client = mock_client({"stdout": "", "stderr": "", "exit_code": 0})
    handle = _DaytonaHandle(
        client=client,
        sandbox_id="sb-1",
        worktree_path=Path("/workspace"),
        host_worktree_path=target,
        baseline={Path("to_delete.txt"): "old-hash"},
    )
    fr = handle.finalize(target=target)
    assert fr.applied is True
    assert not (target / "to_delete.txt").exists()


def test_finalize_returns_not_applied_on_snapshot_failure(tmp_path: Path) -> None:
    """REST failure during finalize snapshot soft-fails."""
    from eden.sandboxes.daytona import _DaytonaHandle

    client = MagicMock(spec=RestClient)
    client.post.side_effect = RuntimeError("network down")
    handle = _DaytonaHandle(
        client=client,
        sandbox_id="sb-1",
        worktree_path=Path("/workspace"),
        host_worktree_path=tmp_path,
        baseline={},
    )
    fr = handle.finalize(target=tmp_path)
    assert fr.applied is False
