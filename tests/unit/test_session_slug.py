"""Verify Claude Code's projects-dir slug derivation."""

from __future__ import annotations

from pathlib import Path, PurePosixPath, PureWindowsPath

import pytest

import eden
from eden.session._slug import claude_projects_slug

pytestmark = pytest.mark.unit


def test_simple_posix_path() -> None:
    assert claude_projects_slug(PurePosixPath("/Users/x/work/eden")) == "-Users-x-work-eden"


def test_workspace_root() -> None:
    assert claude_projects_slug(PurePosixPath("/workspace")) == "-workspace"


def test_relative_path_resolved_through_absolute() -> None:
    """Relative paths get absolutized before slugging.

    The function accepts any path-like; users typically pass an absolute Path
    already (because the orchestrator does), but a sandbox cwd that's relative
    must still produce a deterministic slug.
    """
    p = PurePosixPath("/Users/x/work/eden/sub")
    assert claude_projects_slug(p) == "-Users-x-work-eden-sub"


def test_windows_backslashes_collapse() -> None:
    """A Windows-style path with backslashes maps each separator to dash."""
    assert claude_projects_slug(PureWindowsPath(r"C:\Users\x\work\eden")) == "C--Users-x-work-eden"


def test_trailing_slash_ignored() -> None:
    assert claude_projects_slug(PurePosixPath("/Users/x/work/eden/")) == "-Users-x-work-eden"


def test_public_claude_session_paths(tmp_path: Path) -> None:
    projects_dir = tmp_path / "projects"
    assert eden.encode_project_path(PurePosixPath("/workspace")) == "-workspace"
    assert (
        eden.claude_host_session_path(
            PurePosixPath("/workspace"),
            "sess",
            projects_dir=projects_dir,
        )
        == projects_dir / "-workspace" / "sess.jsonl"
    )
    assert (
        eden.claude_sandbox_session_path(
            PurePosixPath("/workspace"),
            "sess",
            projects_dir=PurePosixPath("/root/.claude/projects"),
        ).as_posix()
        == "/root/.claude/projects/-workspace/sess.jsonl"
    )


def test_public_claude_host_lookup(tmp_path: Path) -> None:
    target = tmp_path / "projects" / "-workspace" / "sess.jsonl"
    target.parent.mkdir(parents=True)
    target.write_text("{}\n", encoding="utf-8")

    assert eden.find_claude_session_on_host("sess", projects_dir=tmp_path / "projects") == target
    assert eden.find_claude_session_on_host("missing", projects_dir=tmp_path / "projects") is None
