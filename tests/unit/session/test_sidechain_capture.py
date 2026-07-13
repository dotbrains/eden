"""Unit tests for Claude subagent/workflow (sidechain) transcript capture.

``capture_sidechain_sessions`` curates separate-file subagent transcripts
(``isSidechain: true``) into ``.eden/sessions/<branch>/iter-N-sub-<id>.jsonl``
next to the main session, path-rewritten, scoped to the run via ``since``.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from eden.session import capture_sidechain_sessions
from eden.session._slug import claude_projects_slug

pytestmark = pytest.mark.unit


def _write_session(slug_dir: Path, session_id: str, *, sidechain: bool, cwd: str) -> Path:
    slug_dir.mkdir(parents=True, exist_ok=True)
    path = slug_dir / f"{session_id}.jsonl"
    rows = [
        {"type": "user", "sessionId": session_id, "isSidechain": sidechain, "cwd": cwd},
        {"type": "assistant", "sessionId": session_id, "isSidechain": sidechain, "cwd": cwd},
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return path


def _setup(tmp_path: Path) -> tuple[Path, Path, str]:
    """Return (home, host_repo, sandbox_cwd) wired so the slug resolves."""
    home = tmp_path / "home"
    host_repo = tmp_path / "repo"
    host_repo.mkdir()
    sandbox_cwd = host_repo  # no-sandbox style: agent cwd == host repo
    slug = claude_projects_slug(sandbox_cwd)
    slug_dir = home / ".claude" / "projects" / slug
    slug_dir.mkdir(parents=True, exist_ok=True)
    return home, host_repo, str(sandbox_cwd)


def test_captures_separate_sidechain_file(tmp_path: Path) -> None:
    home, host_repo, cwd = _setup(tmp_path)
    slug_dir = home / ".claude" / "projects" / claude_projects_slug(Path(cwd))
    _write_session(slug_dir, "main-1", sidechain=False, cwd=cwd)
    _write_session(slug_dir, "sub-1", sidechain=True, cwd=cwd)

    captured = capture_sidechain_sessions(
        main_session_id="main-1",
        sandbox_cwd=Path(cwd),
        host_repo_path=host_repo,
        branch="feat/x",
        iteration=0,
        home=home,
    )

    assert len(captured) == 1
    dest = captured[0]
    assert dest.name == "iter-0-sub-sub-1.jsonl"
    assert dest.parent == host_repo / ".eden" / "sessions" / "feat-x"
    assert dest.is_file()


def test_excludes_main_session_and_non_sidechain(tmp_path: Path) -> None:
    home, host_repo, cwd = _setup(tmp_path)
    slug_dir = home / ".claude" / "projects" / claude_projects_slug(Path(cwd))
    _write_session(slug_dir, "main-1", sidechain=False, cwd=cwd)
    # A plain (non-sidechain) sibling session must not be captured.
    _write_session(slug_dir, "other-2", sidechain=False, cwd=cwd)

    captured = capture_sidechain_sessions(
        main_session_id="main-1",
        sandbox_cwd=Path(cwd),
        host_repo_path=host_repo,
        branch="b",
        iteration=0,
        home=home,
    )

    assert captured == []


def test_since_excludes_stale_files(tmp_path: Path) -> None:
    home, host_repo, cwd = _setup(tmp_path)
    slug_dir = home / ".claude" / "projects" / claude_projects_slug(Path(cwd))
    stale = _write_session(slug_dir, "old-sub", sidechain=True, cwd=cwd)
    # Backdate the stale file well before the run window.
    old = time.time() - 3600
    import os

    os.utime(stale, (old, old))

    captured = capture_sidechain_sessions(
        main_session_id="main-1",
        sandbox_cwd=Path(cwd),
        host_repo_path=host_repo,
        branch="b",
        iteration=0,
        since=time.time() - 60,
        home=home,
    )

    assert captured == []


def test_rewrites_sandbox_paths_to_host(tmp_path: Path) -> None:
    home = tmp_path / "home"
    host_repo = tmp_path / "repo"
    host_repo.mkdir()
    sandbox_cwd = Path("/workspace")  # containerized: cwd differs from host
    slug_dir = home / ".claude" / "projects" / claude_projects_slug(sandbox_cwd)
    _write_session(slug_dir, "sub-1", sidechain=True, cwd="/workspace")

    captured = capture_sidechain_sessions(
        main_session_id="main-1",
        sandbox_cwd=sandbox_cwd,
        host_repo_path=host_repo,
        branch="b",
        iteration=2,
        home=home,
    )

    assert len(captured) == 1
    # Parse rather than substring-match: on Windows the rewritten host path is
    # JSON-escaped (``\\``), so a raw ``str(host_repo)`` check would miss it.
    rows = [
        json.loads(line)
        for line in captured[0].read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert rows
    assert all(row["cwd"] == str(host_repo) for row in rows)
    assert all("/workspace" not in row["cwd"] for row in rows)


def test_non_dict_json_lines_do_not_crash_scan(tmp_path: Path) -> None:
    # A JSONL line that decodes to a non-object (list/number/string) must not
    # raise from the sidechain scan — best-effort contract.
    home, host_repo, cwd = _setup(tmp_path)
    slug_dir = home / ".claude" / "projects" / claude_projects_slug(Path(cwd))
    path = slug_dir / "sub-1.jsonl"
    path.write_text(
        "[1, 2, 3]\n"
        '"just a string with isSidechain in it"\n'
        "42\n" + json.dumps({"type": "user", "isSidechain": True, "cwd": cwd}) + "\n",
        encoding="utf-8",
    )

    captured = capture_sidechain_sessions(
        main_session_id="main-1",
        sandbox_cwd=Path(cwd),
        host_repo_path=host_repo,
        branch="b",
        iteration=0,
        home=home,
    )

    assert len(captured) == 1


def test_missing_slug_dir_is_best_effort(tmp_path: Path) -> None:
    captured = capture_sidechain_sessions(
        main_session_id="main-1",
        sandbox_cwd=tmp_path / "nope",
        host_repo_path=tmp_path / "repo",
        branch="b",
        iteration=0,
        home=tmp_path / "empty-home",
    )
    assert captured == []
