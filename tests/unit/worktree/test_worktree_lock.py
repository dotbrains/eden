"""Verify cross-platform advisory file lock with stale-PID recovery."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from eden.worktree._lock import acquire_lock
from eden.worktree.errors import WorktreeLocked

pytestmark = pytest.mark.unit


def test_acquire_creates_lock_file_with_pid(tmp_path: Path) -> None:
    p = tmp_path / "lock"
    h = acquire_lock(p)
    try:
        assert p.exists()
        assert p.read_text().strip() == str(os.getpid())
    finally:
        h.release()


def test_release_removes_lock_file(tmp_path: Path) -> None:
    p = tmp_path / "lock"
    h = acquire_lock(p)
    h.release()
    assert not p.exists()


def test_release_is_idempotent(tmp_path: Path) -> None:
    p = tmp_path / "lock"
    h = acquire_lock(p)
    h.release()
    h.release()  # should not raise


def test_acquire_creates_parent_directory(tmp_path: Path) -> None:
    p = tmp_path / "nested" / "deeper" / "lock"
    h = acquire_lock(p)
    try:
        assert p.exists()
    finally:
        h.release()


def test_recovers_from_stale_dead_pid(tmp_path: Path) -> None:
    p = tmp_path / "lock"
    p.parent.mkdir(parents=True, exist_ok=True)
    # Use a definitely-dead PID (2**31 - 1 is way past any normal PID range).
    dead_pid = 2**31 - 1
    p.write_text(str(dead_pid))
    h = acquire_lock(p)
    try:
        assert p.read_text().strip() == str(os.getpid())
    finally:
        h.release()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX-only flock test")
def test_blocks_when_holder_alive(tmp_path: Path) -> None:
    p = tmp_path / "lock"
    h = acquire_lock(p)
    try:
        # The current process holds the lock — a sibling acquire from the
        # same process raises because flock is per-fd in this code path
        # AND we read our own pid as the holder.
        with pytest.raises(WorktreeLocked) as excinfo:
            acquire_lock(p)
        assert excinfo.value.lock_path == p
        assert excinfo.value.holder_pid == os.getpid()
    finally:
        h.release()


def test_corrupt_pid_file_treated_as_stale(tmp_path: Path) -> None:
    p = tmp_path / "lock"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("not-a-number")
    h = acquire_lock(p)
    try:
        assert p.read_text().strip() == str(os.getpid())
    finally:
        h.release()
