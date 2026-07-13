"""E2E: interactive abort handling."""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

import pytest

import eden
from eden.agents.cli import cli_agent
from eden.sandboxes.no_sandbox import provider as no_sandbox
from tests.e2e.interactive_helpers import exit_zero_agent

pytestmark = pytest.mark.e2e


def test_interactive_rejects_pre_aborted_signal(e2e_git_repo: Path) -> None:
    ctrl = eden.AbortController()
    ctrl.abort(reason="stop")

    with pytest.raises(eden.Aborted) as ex:
        eden.interactive(agent=exit_zero_agent(), sandbox=no_sandbox(), signal=ctrl.signal)

    assert ex.value.reason == "stop"


def test_interactive_aborts_running_session(e2e_git_repo: Path) -> None:
    ctrl = eden.AbortController()

    def _abort_soon() -> None:
        time.sleep(0.2)
        ctrl.abort(reason="stop")

    thread = threading.Thread(target=_abort_soon, daemon=True)
    thread.start()
    try:
        with pytest.raises(eden.Aborted) as ex:
            eden.interactive(
                agent=cli_agent(
                    name="sleepy",
                    model="x",
                    binary="ignored",
                    build_argv=lambda _ctx: [
                        sys.executable,
                        "-c",
                        "import time; time.sleep(30)",
                    ],
                ),
                sandbox=no_sandbox(),
                signal=ctrl.signal,
            )
    finally:
        thread.join(timeout=2.0)

    assert ex.value.reason == "stop"


def test_worktree_interactive_rejects_pre_aborted_signal(e2e_git_repo: Path) -> None:
    ctrl = eden.AbortController()
    ctrl.abort(reason="stop")

    with eden.create_worktree() as wt:
        with pytest.raises(eden.Aborted) as ex:
            wt.interactive(agent=exit_zero_agent(), sandbox=no_sandbox(), signal=ctrl.signal)

    assert ex.value.reason == "stop"
