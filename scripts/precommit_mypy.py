"""Pre-commit wrapper: locate the project's mypy and exec it.

The mypy hook uses ``language: system`` so it can type-check against the
project's full transitive dependency tree (typer, rich, opentelemetry, ...).
That tree is installed in the developer's ``.venv``, but the venv is not
always on ``PATH`` at commit time — particularly under fish, where
``activate.fish`` is a separate command, or when committing from an editor
that inherits the system shell.

Resolution order:

1. ``.venv/bin/mypy``       (POSIX layout)
2. ``.venv/Scripts/mypy.exe`` (Windows layout)
3. ``mypy`` on ``PATH``    (CI runners install the package globally)

If none is found we print an actionable error and exit non-zero so the
commit is blocked with a useful message instead of a cryptic
``Executable `mypy` not found``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def _find_mypy() -> str | None:
    repo = Path(__file__).resolve().parent.parent
    candidates = [
        repo / ".venv" / "bin" / "mypy",
        repo / ".venv" / "Scripts" / "mypy.exe",
    ]
    for c in candidates:
        if c.is_file() and os.access(c, os.X_OK):
            return str(c)
    return shutil.which("mypy")


def main() -> int:
    mypy = _find_mypy()
    if mypy is None:
        sys.stderr.write(
            "precommit_mypy: could not find mypy.\n"
            "  Install dev deps into .venv: `python -m pip install -e \".[dev]\"`\n"
            "  Or expose mypy on PATH (e.g. `pip install mypy` system-wide).\n",
        )
        return 1
    return subprocess.call([mypy, *sys.argv[1:]])


if __name__ == "__main__":
    raise SystemExit(main())
