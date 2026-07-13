"""Check line-count and flat-directory budgets for active project files."""

from __future__ import annotations

import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FileBudget:
    pattern: str
    max_lines: int
    excludes: tuple[str, ...] = ()


@dataclass(frozen=True)
class DirectoryBudget:
    root: str
    max_files: int


FILE_BUDGETS = (
    FileBudget("eden/**/*.py", 227),
    FileBudget("tests/**/*.py", 231),
    FileBudget("docs/**/*.md", 188, excludes=("docs/superpowers/**",)),
)

DIRECTORY_BUDGETS = (
    DirectoryBudget("eden", 15),
    DirectoryBudget("tests", 11),
)


def _tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files"],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    )
    return [Path(line) for line in result.stdout.splitlines() if line]


def _matches(path: Path, pattern: str) -> bool:
    return path.match(pattern)


def _excluded(path: Path, patterns: tuple[str, ...]) -> bool:
    return any(_matches(path, pattern) for pattern in patterns)


def _line_count(path: Path) -> int:
    with path.open("rb") as handle:
        return sum(1 for _ in handle)


def _file_budget_errors(files: list[Path]) -> list[str]:
    errors: list[str] = []
    for budget in FILE_BUDGETS:
        over: list[tuple[int, Path]] = []
        for path in files:
            if not _matches(path, budget.pattern) or _excluded(path, budget.excludes):
                continue
            count = _line_count(path)
            if count > budget.max_lines:
                over.append((count, path))
        for count, path in sorted(over, reverse=True):
            errors.append(f"{path}: {count} lines exceeds {budget.max_lines}")
    return errors


def _directory_budget_errors(files: list[Path]) -> list[str]:
    errors: list[str] = []
    for budget in DIRECTORY_BUDGETS:
        counts: Counter[Path] = Counter()
        for path in files:
            if not path.parts or path.parts[0] != budget.root or not path.is_file():
                continue
            counts[path.parent] += 1
        for directory, count in sorted(counts.items(), key=lambda item: (-item[1], str(item[0]))):
            if count > budget.max_files:
                errors.append(f"{directory}: {count} files exceeds {budget.max_files}")
    return errors


def main() -> int:
    files = [path for path in _tracked_files() if path.is_file()]
    errors = [*_file_budget_errors(files), *_directory_budget_errors(files)]
    if not errors:
        return 0
    sys.stderr.write("LOC budget check failed:\n")
    for error in errors:
        sys.stderr.write(f"  - {error}\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
