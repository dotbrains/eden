"""Verify no_sandbox interactive exec behavior."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from eden.sandboxes.no_sandbox import provider
from tests.unit.no_sandbox.conftest import opts

pytestmark = pytest.mark.unit


def test_interactive_exec_runs_argv_with_inherited_stdio(tmp_path: Path) -> None:
    """``interactive_exec`` runs the argv with stdio inherited; returns exit code."""
    handle = provider().create(opts(tmp_path))
    try:
        rc = handle.interactive_exec(  # type: ignore[attr-defined]
            [sys.executable, "-c", "import sys; sys.exit(0)"],
        )
        assert rc == 0

        rc7 = handle.interactive_exec(  # type: ignore[attr-defined]
            [sys.executable, "-c", "import sys; sys.exit(7)"],
        )
        assert rc7 == 7
    finally:
        handle.close()


def test_interactive_exec_uses_provided_cwd(tmp_path: Path) -> None:
    """When cwd is given, the subprocess starts there."""
    handle = provider().create(opts(tmp_path))
    out = tmp_path / "where.txt"
    target = tmp_path / "subdir"
    target.mkdir()
    try:
        rc = handle.interactive_exec(  # type: ignore[attr-defined]
            [
                sys.executable,
                "-c",
                f"import os; open({str(out)!r}, 'w').write(os.getcwd())",
            ],
            cwd=target,
        )
        assert rc == 0
        assert Path(out.read_text()).resolve() == target.resolve()
    finally:
        handle.close()
