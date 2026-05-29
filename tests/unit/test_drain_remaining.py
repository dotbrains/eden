"""Verify the bounded-drain behaviour of ``_AgentRunner.drain_remaining``.

The completion-timeout port (sandcastle v0.6.6, ddc26ba) bounds the
total wall-time spent draining trailing lines after a completion-signal
match, so a child process that holds the stdout pipe open can't hang
the iteration until ``idle_timeout`` (10 min) trips.
"""

from __future__ import annotations

import threading
import time
from queue import Queue
from typing import Any

import pytest

from eden.orchestrator._runner import _SENTINEL, _AgentRunner

pytestmark = pytest.mark.unit


def _make_runner_with_queue(items: list[Any] | None = None) -> _AgentRunner:
    """Build a runner whose stdout queue is pre-populated for testing."""
    # The constructor needs argv/env/watchdog but we bypass __enter__ and only
    # exercise drain_remaining, which touches just ``_stdout_q``.
    runner = _AgentRunner.__new__(_AgentRunner)
    runner._stdout_q = Queue()
    if items is not None:
        for item in items:
            runner._stdout_q.put(item)
    return runner


def test_drain_returns_immediately_on_sentinel() -> None:
    runner = _make_runner_with_queue(["line1\n", "line2\n", _SENTINEL])
    result = runner.drain_remaining(total_timeout=10.0, per_item_timeout=0.1)
    assert result.lines == ["line1", "line2"]
    assert result.timed_out is False


def test_drain_exits_idle_when_queue_empty_for_per_item_timeout() -> None:
    """No more lines for ``per_item_timeout`` → idle exit, not timeout."""
    runner = _make_runner_with_queue(["line1\n"])
    start = time.monotonic()
    result = runner.drain_remaining(total_timeout=10.0, per_item_timeout=0.05)
    elapsed = time.monotonic() - start
    assert result.lines == ["line1"]
    assert result.timed_out is False
    # Should exit ~per_item_timeout after the last line, well before the
    # 10s total budget.
    assert elapsed < 1.0


def test_drain_times_out_when_lines_keep_arriving_past_budget() -> None:
    """A noisy child that prints every 50ms forever should hit total_timeout."""
    runner = _make_runner_with_queue()

    stop = threading.Event()

    def _spam() -> None:
        while not stop.is_set():
            runner._stdout_q.put("noise\n")
            time.sleep(0.05)

    t = threading.Thread(target=_spam, daemon=True)
    t.start()
    try:
        start = time.monotonic()
        # total_timeout 0.3s, per_item 0.2s — items arrive every 50ms so
        # idle exit can't trigger; we must hit total_timeout.
        result = runner.drain_remaining(total_timeout=0.3, per_item_timeout=0.2)
        elapsed = time.monotonic() - start
    finally:
        stop.set()
        t.join(timeout=1.0)

    assert result.timed_out is True
    # Elapsed should be very close to total_timeout, not the per_item budget
    # multiplied by line count.
    assert 0.25 <= elapsed <= 0.7
    # We accumulated some noise — at least one line.
    assert len(result.lines) >= 1


def test_drain_total_timeout_none_falls_back_to_idle_only() -> None:
    """``total_timeout=None`` preserves the pre-v0.6.6 unbounded behaviour."""
    runner = _make_runner_with_queue(["line1\n", _SENTINEL])
    result = runner.drain_remaining(total_timeout=None, per_item_timeout=0.05)
    assert result.lines == ["line1"]
    assert result.timed_out is False
