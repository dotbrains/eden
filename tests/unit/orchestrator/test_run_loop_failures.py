"""Verify _run_loop abort and timeout paths."""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from eden._types import Timeouts
from eden.abort import AbortController
from eden.agents import simulated_agent
from eden.errors import Aborted, IdleTimeout
from eden.lifecycle import Hooks
from eden.orchestrator import run
from eden.orchestrator._setup import SetupResult, resolve_setup
from eden.orchestrator.loop import _run_loop
from eden.sandboxes.no_sandbox import provider as no_sandbox_provider

pytestmark = pytest.mark.unit


def _setup(tmp_git_repo: Path) -> SetupResult:
    return resolve_setup(
        prompt="please complete",
        prompt_file=None,
        prompt_args=None,
        cwd=tmp_git_repo,
        env=None,
        provider_env={},
        sandbox_kind="none",
    )


def test_run_loop_aborts_when_signal_set(tmp_git_repo: Path) -> None:
    agent = simulated_agent(output=["a"] * 50, delay_per_line=0.05)
    setup = _setup(tmp_git_repo)
    ctrl = AbortController()

    def trigger() -> None:
        time.sleep(0.1)
        ctrl.abort(reason="test")

    threading.Thread(target=trigger).start()
    with pytest.raises(Aborted):
        _run_loop(
            agent=agent,
            sandbox=no_sandbox_provider(),
            setup=setup,
            branch_strategy=None,
            max_iterations=1,
            completion_signal="NEVER",
            idle_timeout=10.0,
            idle_warning_interval=None,
            name=None,
            hooks=Hooks(),
            timeouts=Timeouts(),
            on_event=None,
            logging_cfg=None,
            signal=ctrl.signal,
            prompt_args=None,
        )


def test_run_rejects_pre_aborted_signal_before_setup(tmp_git_repo: Path) -> None:
    ctrl = AbortController()
    ctrl.abort(reason="cancelled-before-start")

    with pytest.raises(Aborted) as ex:
        run(
            agent=simulated_agent(),
            sandbox=no_sandbox_provider(),
            prompt_file=tmp_git_repo / "missing.md",
            cwd=tmp_git_repo,
            signal=ctrl.signal,
        )

    assert ex.value.reason == "cancelled-before-start"


def test_run_loop_idle_timeout(tmp_git_repo: Path) -> None:
    agent = simulated_agent(output=["a"] * 30, delay_per_line=2.0)
    setup = _setup(tmp_git_repo)
    ctrl = AbortController()
    with pytest.raises(IdleTimeout):
        _run_loop(
            agent=agent,
            sandbox=no_sandbox_provider(),
            setup=setup,
            branch_strategy=None,
            max_iterations=1,
            completion_signal="NEVER",
            idle_timeout=0.3,
            idle_warning_interval=None,
            name=None,
            hooks=Hooks(),
            timeouts=Timeouts(),
            on_event=None,
            logging_cfg=None,
            signal=ctrl.signal,
            prompt_args=None,
        )
