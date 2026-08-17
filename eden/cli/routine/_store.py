"""Persistence for named ``eden routine`` configs under ``.eden/routines/``.

Routine files are plain JSON, one per name. Unlike ``.eden/{logs,sessions,
worktrees,isolated}``, ``.eden/routines/`` is never touched by ``eden clean``
and isn't listed in the scaffolded ``.gitignore`` — routines are meant to be
committed, so history/versioning comes from git itself rather than a bespoke
scheme.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


@dataclass(frozen=True)
class RoutineConfig:
    sandbox: str
    agent: str
    model: str
    template: str
    backlog: str
    image_name: str | None
    max_iterations: int
    idle_timeout: float
    completion_timeout: float | None


def routines_dir(cwd: Path) -> Path:
    return cwd / ".eden" / "routines"


def routine_path(cwd: Path, name: str) -> Path:
    if not _NAME_RE.fullmatch(name):
        raise ValueError(
            f"routine name {name!r} must start with a letter or digit and contain only "
            "letters, digits, '.', '_', or '-'"
        )
    return routines_dir(cwd) / f"{name}.json"


def save_routine(cwd: Path, name: str, config: RoutineConfig) -> Path:
    path = routine_path(cwd, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(config), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_routine(cwd: Path, name: str) -> RoutineConfig:
    path = routine_path(cwd, name)
    if not path.is_file():
        raise FileNotFoundError(f"no routine named {name!r} in {routines_dir(cwd)}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return RoutineConfig(**data)


def list_routines(cwd: Path) -> list[str]:
    directory = routines_dir(cwd)
    if not directory.is_dir():
        return []
    return sorted(p.stem for p in directory.glob("*.json"))


def delete_routine(cwd: Path, name: str) -> bool:
    path = routine_path(cwd, name)
    if not path.is_file():
        return False
    path.unlink()
    return True


__all__ = [
    "RoutineConfig",
    "delete_routine",
    "list_routines",
    "load_routine",
    "routine_path",
    "routines_dir",
    "save_routine",
]
