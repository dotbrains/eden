"""Verify the codex SessionStorage + dated-directory walker."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eden.providers._types import Mount
from eden.session._codex import CodexSessionStorage, find_codex_session_path

pytestmark = pytest.mark.unit


def _seed(home: Path, *, year: str, month: str, day: str, name: str, body: str = "") -> Path:
    """Create a fake codex session file at home/.codex/sessions/<Y>/<M>/<D>/<name>."""
    target_dir = home / ".codex" / "sessions" / year / month / day
    target_dir.mkdir(parents=True, exist_ok=True)
    f = target_dir / name
    f.write_text(body, encoding="utf-8")
    return f


def test_find_returns_none_when_root_missing(tmp_path: Path) -> None:
    assert find_codex_session_path(tmp_path / "does-not-exist", "abc") is None


def test_find_locates_rollout_file_by_session_id(tmp_path: Path) -> None:
    f = _seed(
        tmp_path,
        year="2026",
        month="05",
        day="26",
        name="rollout-20260526T100000-abc123.jsonl",
    )
    found = find_codex_session_path(tmp_path / ".codex" / "sessions", "abc123")
    assert found == f


def test_find_skips_non_matching_filenames(tmp_path: Path) -> None:
    _seed(
        tmp_path,
        year="2026",
        month="05",
        day="26",
        name="rollout-20260526T100000-other-id.jsonl",
    )
    found = find_codex_session_path(tmp_path / ".codex" / "sessions", "abc123")
    assert found is None


def test_find_requires_rollout_prefix(tmp_path: Path) -> None:
    _seed(tmp_path, year="2026", month="05", day="26", name="other-abc123.jsonl")
    assert find_codex_session_path(tmp_path / ".codex" / "sessions", "abc123") is None


def test_find_walks_deep_subdirs(tmp_path: Path) -> None:
    f = _seed(
        tmp_path,
        year="2024",
        month="12",
        day="31",
        name="rollout-old-deep.jsonl",
    )
    assert find_codex_session_path(tmp_path / ".codex" / "sessions", "deep") == f


def test_extra_mounts_empty_when_sessions_dir_missing(tmp_path: Path) -> None:
    s = CodexSessionStorage(home=tmp_path)
    assert s.extra_mounts() == ()


def test_extra_mounts_returns_mount_when_sessions_dir_exists(tmp_path: Path) -> None:
    (tmp_path / ".codex" / "sessions").mkdir(parents=True)
    s = CodexSessionStorage(home=tmp_path)
    mounts = s.extra_mounts()
    assert len(mounts) == 1
    assert isinstance(mounts[0], Mount)
    assert mounts[0].host == tmp_path / ".codex" / "sessions"
    # Sandbox paths are always POSIX; compare via as_posix() so the
    # assertion passes on Windows hosts too (str(WindowsPath("/foo/bar"))
    # produces backslashes).
    assert mounts[0].sandbox.as_posix() == "/home/agent/.codex/sessions"


class _StubHandle:
    def __init__(self, wt: Path) -> None:
        self.worktree_path = wt

    def exec(self, *a: object, **k: object) -> object: ...
    def copy_file_in(self, *a: object, **k: object) -> None: ...
    def copy_file_out(self, *a: object, **k: object) -> None: ...
    def close(self) -> None: ...


def test_host_capture_writes_per_iteration_copy(tmp_path: Path) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    repo.mkdir()
    # Seed a fake codex JSONL with one line that mentions /workspace
    src = _seed(
        home,
        year="2026",
        month="05",
        day="26",
        name="rollout-20260526T100000-sess1.jsonl",
        body=json.dumps({"cwd": "/workspace", "msg": "hi"}) + "\n",
    )
    handle = _StubHandle(wt=Path("/workspace"))
    s = CodexSessionStorage(home=home)
    dest = s.host_capture(
        handle=handle,  # type: ignore[arg-type]
        session_id="sess1",
        host_repo_path=repo,
        branch="feat/x",
        iteration=2,
    )
    assert dest is not None
    assert dest.parent == repo / ".eden" / "sessions" / "feat-x"
    assert dest.name == "iter-2-sess1.jsonl"
    body = dest.read_text(encoding="utf-8")
    # Parse the JSONL line and compare decoded values: on Windows, host
    # paths contain backslashes that JSON serializes as ``\\``, so a raw
    # substring check on the file body would fail even when the rewrite
    # was correct. The decoded ``cwd`` field is OS-correct.
    entry = json.loads(body.strip())
    assert entry["cwd"] == str(repo)
    assert "/workspace" not in body
    # Source unchanged.
    assert src.read_text(encoding="utf-8").startswith("{")


def test_host_capture_returns_none_when_session_missing(tmp_path: Path) -> None:
    home = tmp_path / "home"
    (home / ".codex" / "sessions").mkdir(parents=True)
    repo = tmp_path / "repo"
    repo.mkdir()
    handle = _StubHandle(wt=Path("/workspace"))
    s = CodexSessionStorage(home=home)
    assert (
        s.host_capture(
            handle=handle,  # type: ignore[arg-type]
            session_id="missing",
            host_repo_path=repo,
            branch="b",
            iteration=0,
        )
        is None
    )


def test_sandbox_transfer_is_noop(tmp_path: Path) -> None:
    s = CodexSessionStorage(home=tmp_path)
    handle = _StubHandle(wt=Path("/workspace"))
    # Returns None (no value); just check it does not raise.
    s.sandbox_transfer(
        handle=handle,  # type: ignore[arg-type]
        host_session_file=tmp_path / "x.jsonl",
        session_id="any",
    )
