"""Verify the new cwd kwarg on _AgentRunner."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from eden.abort import AbortController
from eden.orchestrator._idle import IdleWatchdog
from eden.orchestrator._runner import _AgentRunner

pytestmark = pytest.mark.unit


def test_default_cwd_inherits_python_cwd(tmp_path: Path) -> None:
    """Without cwd= the agent runs with the parent's cwd (Phase 3a default)."""
    argv = [sys.executable, "-c", "import os, sys; sys.stdout.write(os.getcwd())"]
    wd = IdleWatchdog(idle_timeout=10.0, idle_warning_interval=None)
    wd.start()
    try:
        with _AgentRunner(argv=argv, env={}, watchdog=wd) as runner:
            ctrl = AbortController()
            lines = list(runner.iter_lines(signal=ctrl.signal, on_warning=lambda _m: None))
        assert lines == [str(Path.cwd())]
    finally:
        wd.stop()


def test_cwd_kwarg_changes_subprocess_cwd(tmp_path: Path) -> None:
    """With cwd=tmp_path the agent runs in tmp_path."""
    argv = [sys.executable, "-c", "import os, sys; sys.stdout.write(os.getcwd())"]
    wd = IdleWatchdog(idle_timeout=10.0, idle_warning_interval=None)
    wd.start()
    try:
        with _AgentRunner(argv=argv, env={}, watchdog=wd, cwd=tmp_path) as runner:
            ctrl = AbortController()
            lines = list(runner.iter_lines(signal=ctrl.signal, on_warning=lambda _m: None))
        # The path may be normalized (e.g., /private/var/folders/... vs /var/folders/... on macOS)
        assert Path(lines[0]).resolve() == tmp_path.resolve()
    finally:
        wd.stop()


def test_explicit_none_cwd_matches_default(tmp_path: Path) -> None:
    argv = [sys.executable, "-c", "import os, sys; sys.stdout.write(os.getcwd())"]
    wd = IdleWatchdog(idle_timeout=10.0, idle_warning_interval=None)
    wd.start()
    try:
        with _AgentRunner(argv=argv, env={}, watchdog=wd, cwd=None) as runner:
            ctrl = AbortController()
            lines = list(runner.iter_lines(signal=ctrl.signal, on_warning=lambda _m: None))
        assert lines == [str(Path.cwd())]
    finally:
        wd.stop()
