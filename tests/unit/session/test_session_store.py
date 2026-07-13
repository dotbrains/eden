"""Verify capture_session: locate ~/.claude/projects/<slug>/<id>.jsonl, copy + rewrite."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eden.errors import SessionCaptureFailed
from eden.session import capture_session
from eden.session._slug import claude_projects_slug

pytestmark = pytest.mark.unit


def _write_source(home: Path, slug: str, session_id: str, lines: list[dict[str, object]]) -> Path:
    src_dir = home / ".claude" / "projects" / slug
    src_dir.mkdir(parents=True, exist_ok=True)
    src = src_dir / f"{session_id}.jsonl"
    src.write_text("\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8")
    return src


def test_happy_path_no_sandbox(tmp_path: Path) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    repo.mkdir()
    src = _write_source(
        home,
        slug=claude_projects_slug(repo),
        session_id="abc-123",
        lines=[{"cwd": str(repo)}, {"text": "hello"}],
    )
    dest = capture_session(
        session_id="abc-123",
        sandbox_cwd=repo,
        host_repo_path=repo,
        branch="HEAD",
        iteration=0,
        home=home,
    )
    assert dest.exists()
    assert dest.parent == repo / ".eden" / "sessions" / "HEAD"
    assert dest.name == "iter-0-abc-123.jsonl"
    body_lines = dest.read_text(encoding="utf-8").strip().split("\n")
    assert json.loads(body_lines[0]) == {"cwd": str(repo)}
    assert json.loads(body_lines[1]) == {"text": "hello"}
    assert src.exists()  # source not deleted


def test_path_rewriting_for_sandboxed_run(tmp_path: Path) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "host_repo"
    repo.mkdir()
    sandbox_cwd = Path("/workspace")
    src = _write_source(
        home,
        slug=claude_projects_slug(sandbox_cwd),
        session_id="def-456",
        lines=[
            {"cwd": "/workspace"},
            {"tool_input": {"file_path": "/workspace/src/x.py"}},
        ],
    )
    dest = capture_session(
        session_id="def-456",
        sandbox_cwd=sandbox_cwd,
        host_repo_path=repo,
        branch="feat/x",
        iteration=2,
        home=home,
    )
    body_lines = dest.read_text(encoding="utf-8").strip().split("\n")
    assert json.loads(body_lines[0]) == {"cwd": str(repo)}
    assert json.loads(body_lines[1]) == {"tool_input": {"file_path": str(repo) + "/src/x.py"}}
    # Branch sanitization: "feat/x" -> "feat-x"
    assert dest.parent == repo / ".eden" / "sessions" / "feat-x"
    assert src.exists()


def test_missing_source_raises(tmp_path: Path) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    repo.mkdir()
    with pytest.raises(SessionCaptureFailed) as excinfo:
        capture_session(
            session_id="missing",
            sandbox_cwd=repo,
            host_repo_path=repo,
            branch="HEAD",
            iteration=0,
            home=home,
        )
    assert excinfo.value.code == "session.capture_failed"
    assert "missing" in excinfo.value.message


def test_dest_dir_created(tmp_path: Path) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_source(
        home,
        slug=claude_projects_slug(repo),
        session_id="z",
        lines=[{}],
    )
    # .eden/sessions/HEAD does not exist yet
    dest = capture_session(
        session_id="z",
        sandbox_cwd=repo,
        host_repo_path=repo,
        branch="HEAD",
        iteration=9,
        home=home,
    )
    assert dest.parent.is_dir()
