"""Verify eden.cli.routine._store persistence primitives."""

from __future__ import annotations

from pathlib import Path

import pytest

from eden.cli.routine._store import (
    RoutineConfig,
    delete_routine,
    list_routines,
    load_routine,
    routine_path,
    save_routine,
)

pytestmark = pytest.mark.unit


def _config(**overrides: object) -> RoutineConfig:
    defaults: dict[str, object] = {
        "sandbox": "no-sandbox",
        "agent": "claude-code",
        "model": "claude-opus-4-8",
        "template": "simple-loop",
        "backlog": "github",
        "image_name": None,
        "max_iterations": 3,
        "idle_timeout": 600.0,
        "completion_timeout": 60.0,
    }
    defaults.update(overrides)
    return RoutineConfig(**defaults)  # type: ignore[arg-type]


def test_save_then_load_round_trips(repo_dir: Path) -> None:
    config = _config()
    save_routine(repo_dir, "nightly", config)
    assert load_routine(repo_dir, "nightly") == config


def test_save_writes_under_eden_routines(repo_dir: Path) -> None:
    path = save_routine(repo_dir, "nightly", _config())
    assert path == repo_dir / ".eden" / "routines" / "nightly.json"
    assert path.is_file()


def test_list_routines_empty_when_missing(repo_dir: Path) -> None:
    assert list_routines(repo_dir) == []


def test_list_routines_sorted(repo_dir: Path) -> None:
    save_routine(repo_dir, "zeta", _config())
    save_routine(repo_dir, "alpha", _config())
    assert list_routines(repo_dir) == ["alpha", "zeta"]


def test_load_missing_routine_raises(repo_dir: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_routine(repo_dir, "missing")


def test_delete_routine_removes_file(repo_dir: Path) -> None:
    save_routine(repo_dir, "nightly", _config())
    assert delete_routine(repo_dir, "nightly") is True
    assert list_routines(repo_dir) == []


def test_delete_missing_routine_returns_false(repo_dir: Path) -> None:
    assert delete_routine(repo_dir, "missing") is False


@pytest.mark.parametrize("bad_name", ["../escape", "a/b", ".hidden", ""])
def test_routine_path_rejects_unsafe_names(repo_dir: Path, bad_name: str) -> None:
    with pytest.raises(ValueError, match="routine name"):
        routine_path(repo_dir, bad_name)
