"""Verify _run_loop happy paths + completion + abort + idle."""

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
from eden.logging import Logging
from eden.orchestrator._loop import _run_loop
from eden.orchestrator._setup import SetupResult, resolve_setup
from eden.sandboxes.no_sandbox import provider as no_sandbox_provider
from eden.streaming import StreamEvent

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


def test_run_loop_completion_ends_loop(tmp_git_repo: Path) -> None:
    agent = simulated_agent(output="working\n<promise>COMPLETE</promise>\n")
    setup = _setup(tmp_git_repo)
    ctrl = AbortController()
    result = _run_loop(
        agent=agent,
        sandbox=no_sandbox_provider(),
        setup=setup,
        branch_strategy=None,
        max_iterations=5,
        completion_signal="<promise>COMPLETE</promise>",
        idle_timeout=10.0,
        idle_warning_interval=None,
        name=None,
        hooks=Hooks(),
        timeouts=Timeouts(),
        on_event=None,
        logging_cfg=Logging.file(tmp_git_repo / ".eden" / "logs" / "x.log"),
        signal=ctrl.signal,
        prompt_args=None,
    )
    assert len(result.iterations) == 1
    assert result.completion_signal == "<promise>COMPLETE</promise>"
    assert "working" in result.stdout
    assert result.log_file_path == tmp_git_repo / ".eden" / "logs" / "x.log"


def test_run_loop_max_iterations_exhausted_without_signal(tmp_git_repo: Path) -> None:
    agent = simulated_agent(output="just text\n")
    setup = _setup(tmp_git_repo)
    ctrl = AbortController()
    result = _run_loop(
        agent=agent,
        sandbox=no_sandbox_provider(),
        setup=setup,
        branch_strategy=None,
        max_iterations=2,
        completion_signal="MARKER",
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
    assert len(result.iterations) == 2
    assert result.completion_signal is None


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


def test_run_loop_emits_text_events_via_callback(tmp_git_repo: Path) -> None:
    agent = simulated_agent(output="alpha\n<promise>COMPLETE</promise>\n")
    setup = _setup(tmp_git_repo)
    ctrl = AbortController()
    events: list[StreamEvent] = []
    _run_loop(
        agent=agent,
        sandbox=no_sandbox_provider(),
        setup=setup,
        branch_strategy=None,
        max_iterations=1,
        completion_signal="<promise>COMPLETE</promise>",
        idle_timeout=10.0,
        idle_warning_interval=None,
        name=None,
        hooks=Hooks(),
        timeouts=Timeouts(),
        on_event=events.append,
        logging_cfg=None,
        signal=ctrl.signal,
        prompt_args=None,
    )
    text_events = [e for e in events if e.type == "text"]
    assert any(e.text == "alpha" for e in text_events)


def test_run_loop_simulated_agent_does_not_capture(tmp_git_repo: Path) -> None:
    """simulated_agent lacks captures_sessions → capture skipped → session fields are None."""
    agent = simulated_agent(output="hello\n<promise>COMPLETE</promise>\n")
    setup = _setup(tmp_git_repo)
    ctrl = AbortController()
    result = _run_loop(
        agent=agent,
        sandbox=no_sandbox_provider(),
        setup=setup,
        branch_strategy=None,
        max_iterations=1,
        completion_signal="<promise>COMPLETE</promise>",
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
    assert result.session_id is None
    assert result.session_file_path is None
    assert result.usage is None
    assert result.iterations[0].session_id is None
    assert result.iterations[0].session_file_path is None
    assert result.iterations[0].usage is None
