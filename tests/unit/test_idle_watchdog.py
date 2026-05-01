"""Verify IdleWatchdog timing behaviour."""

from __future__ import annotations

import time

import pytest

from eden.errors import IdleTimeout
from eden.orchestrator._idle import IdleWatchdog

pytestmark = pytest.mark.unit


def test_no_warning_when_activity_keeps_resetting() -> None:
    wd = IdleWatchdog(idle_timeout=0.5, idle_warning_interval=0.1)
    wd.start()
    try:
        for _ in range(8):
            time.sleep(0.05)
            wd.record_activity()
        # No warning should have fired in this 0.4s window because we reset
        # every 0.05s.
        assert wd.poll_warning() is None
    finally:
        wd.stop()


def test_warning_fires_after_interval() -> None:
    wd = IdleWatchdog(idle_timeout=10.0, idle_warning_interval=0.15)
    wd.start()
    try:
        time.sleep(0.4)
        # Two intervals elapsed — at least one warning should be queued.
        warnings: list[int] = []
        while True:
            w = wd.poll_warning()
            if w is None:
                break
            warnings.append(w)
        assert warnings  # at least one warning
        # minutes_idle is rounded — 0 is acceptable for sub-minute warnings.
        assert all(isinstance(m, int) for m in warnings)
    finally:
        wd.stop()


def test_timeout_raises_idle_timeout() -> None:
    wd = IdleWatchdog(idle_timeout=0.2, idle_warning_interval=None)
    wd.start()
    try:
        time.sleep(0.4)
        with pytest.raises(IdleTimeout):
            wd.check_timeout()
    finally:
        wd.stop()


def test_no_warning_interval_disables_warnings() -> None:
    wd = IdleWatchdog(idle_timeout=2.0, idle_warning_interval=None)
    wd.start()
    try:
        time.sleep(0.3)
        assert wd.poll_warning() is None
    finally:
        wd.stop()


def test_stop_is_idempotent() -> None:
    wd = IdleWatchdog(idle_timeout=1.0, idle_warning_interval=None)
    wd.start()
    wd.stop()
    wd.stop()  # must not raise
