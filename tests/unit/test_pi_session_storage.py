"""Verify the pi SessionStorage + encoded-cwd helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eden.providers._types import Mount
from eden.session._pi import (
    PiSessionStorage,
    encode_pi_session_dir,
    find_pi_session_path,
    transfer_pi_session,
)

pytestmark = pytest.mark.unit


def _seed(home: Path, *, enc_dir: str, name: str, body: str = "") -> Path:
    """Create a fake pi session file at home/.pi/agent/sessions/<enc_dir>/<name>."""
    target_dir = home / ".pi" / "agent" / "sessions" / enc_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    f = target_dir / name
    f.write_text(body, encoding="utf-8")
    return f


def test_encode_strips_leading_separator_and_substitutes() -> None:
    assert encode_pi_session_dir(Path("/Users/foo/repo")) == "--Users-foo-repo--"


def test_encode_handles_windows_style_path() -> None:
    """``\\`` and ``:`` both substitute to ``-`` — adjacent separators stay separate."""
    # Pass a raw string through Path; Path on POSIX keeps backslashes literal.
    # ``C:\Users\foo`` → ``C-`` (colon), then ``-Users-foo`` (backslashes) →
    # ``C--Users-foo`` wrapped as ``--C--Users-foo--``.
    enc = encode_pi_session_dir(Path("C:\\Users\\foo"))
    assert enc == "--C--Users-foo--"


def test_find_returns_none_when_root_missing(tmp_path: Path) -> None:
    assert find_pi_session_path(tmp_path / "does-not-exist", "abc") is None


def test_find_locates_session_by_id_suffix(tmp_path: Path) -> None:
    f = _seed(
        tmp_path,
        enc_dir="--workspace--",
        name="20260529T120000_sess-abc.jsonl",
    )
    found = find_pi_session_path(tmp_path / ".pi" / "agent" / "sessions", "sess-abc")
    assert found == f


def test_find_skips_files_at_root(tmp_path: Path) -> None:
    """Sessions must live one level deep inside an ``--enc--`` dir."""
    root = tmp_path / ".pi" / "agent" / "sessions"
    root.mkdir(parents=True, exist_ok=True)
    (root / "20260529T120000_sess-abc.jsonl").write_text("", encoding="utf-8")
    assert find_pi_session_path(root, "sess-abc") is None


def test_find_handles_id_collision_match_on_full_suffix(tmp_path: Path) -> None:
    """``_<id>.jsonl`` is matched as a suffix — substring of id is not a match."""
    _seed(
        tmp_path,
        enc_dir="--workspace--",
        name="20260529T120000_sess-abcd.jsonl",
    )
    assert find_pi_session_path(tmp_path / ".pi" / "agent" / "sessions", "abc") is None


def test_transfer_rewrites_session_header_cwd_only() -> None:
    header = json.dumps({"type": "session", "id": "x", "cwd": "/host/repo"})
    body = json.dumps({"type": "message_update", "delta": "hi"})
    jsonl = f"{header}\n{body}\n"
    out = transfer_pi_session(jsonl, Path("/host/repo"), Path("/workspace"))
    # Header rewritten.
    lines = out.split("\n")
    parsed_header = json.loads(lines[0])
    assert parsed_header["cwd"] == "/workspace"
    # Body line untouched (other than potential trailing newline).
    assert lines[1] == body


def test_transfer_leaves_header_untouched_when_cwd_doesnt_match() -> None:
    """Defence in depth: only rewrite when ``from_cwd`` is the current value."""
    header = json.dumps({"type": "session", "id": "x", "cwd": "/other"})
    out = transfer_pi_session(header + "\n", Path("/host/repo"), Path("/workspace"))
    assert json.loads(out.split("\n")[0])["cwd"] == "/other"


def test_transfer_preserves_malformed_lines() -> None:
    """A junk JSON line passes through verbatim — capture stays byte-faithful."""
    out = transfer_pi_session("not json\n", Path("/a"), Path("/b"))
    assert out == "not json\n"


def test_extra_mounts_empty_when_sessions_dir_missing(tmp_path: Path) -> None:
    storage = PiSessionStorage(home=tmp_path)
    assert storage.extra_mounts() == ()


def test_extra_mounts_returns_pi_sessions_mount(tmp_path: Path) -> None:
    (tmp_path / ".pi" / "agent" / "sessions").mkdir(parents=True)
    storage = PiSessionStorage(home=tmp_path)
    mounts = storage.extra_mounts()
    assert len(mounts) == 1
    m: Mount = mounts[0]
    assert m.host == tmp_path / ".pi" / "agent" / "sessions"
    assert m.sandbox == Path("/home/agent/.pi/agent/sessions")


def test_locate_session_on_host_finds_match(tmp_path: Path) -> None:
    f = _seed(tmp_path, enc_dir="--workspace--", name="ts_sess.jsonl")
    storage = PiSessionStorage(home=tmp_path)
    located = storage.locate_session_on_host(session_id="sess", sandbox_cwd=Path("/anywhere"))
    assert located == f
