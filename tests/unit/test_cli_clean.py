"""Verify `eden clean` real implementation."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest
from typer.testing import CliRunner

from eden.cli.main import app

pytestmark = pytest.mark.unit


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _seed(repo: Path, *, name: str, age_days: int = 0) -> Path:
    """Create ``.eden/<name>/<name>-data.txt`` with mtime ``age_days`` in the past."""
    target = repo / ".eden" / name / f"{name}-data.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("hello", encoding="utf-8")
    if age_days > 0:
        old_ts = time.time() - (age_days * 86400)
        os.utime(target, (old_ts, old_ts))
        # Also age the parent dir entry so the cleaner sees the dir as old.
        os.utime(target.parent, (old_ts, old_ts))
    return target


def test_clean_no_op_when_eden_dir_missing(runner: CliRunner, tmp_path: Path) -> None:
    result = runner.invoke(app, ["clean", "--cwd", str(tmp_path)])
    assert result.exit_code == 0
    combined = (result.output or "") + (result.stderr or "")
    assert "no .eden/" in combined.lower()


def test_clean_removes_old_artifacts_by_age(runner: CliRunner, tmp_path: Path) -> None:
    _seed(tmp_path, name="logs", age_days=30)
    _seed(tmp_path, name="sessions", age_days=0)  # fresh

    result = runner.invoke(app, ["clean", "--cwd", str(tmp_path), "--days", "7"])
    assert result.exit_code == 0, result.output
    # Old logs gone; fresh sessions kept.
    assert not (tmp_path / ".eden" / "logs" / "logs-data.txt").exists()
    assert (tmp_path / ".eden" / "sessions" / "sessions-data.txt").exists()


def test_clean_all_purges_regardless_of_age(runner: CliRunner, tmp_path: Path) -> None:
    _seed(tmp_path, name="logs", age_days=0)
    _seed(tmp_path, name="sessions", age_days=0)

    result = runner.invoke(app, ["clean", "--cwd", str(tmp_path), "--all"])
    assert result.exit_code == 0, result.output
    # Whole subdirs gone.
    assert not (tmp_path / ".eden" / "logs").exists()
    assert not (tmp_path / ".eden" / "sessions").exists()


def test_clean_does_not_touch_scaffolded_files(runner: CliRunner, tmp_path: Path) -> None:
    """Files directly under .eden/ (Dockerfile, prompt.md, etc.) must survive."""
    eden_dir = tmp_path / ".eden"
    eden_dir.mkdir()
    (eden_dir / "Dockerfile").write_text("FROM python:3.13", encoding="utf-8")
    (eden_dir / "prompt.md").write_text("hi", encoding="utf-8")
    _seed(tmp_path, name="logs", age_days=30)

    result = runner.invoke(app, ["clean", "--cwd", str(tmp_path), "--all"])
    assert result.exit_code == 0, result.output
    assert (eden_dir / "Dockerfile").exists()
    assert (eden_dir / "prompt.md").exists()
    assert not (eden_dir / "logs").exists()
