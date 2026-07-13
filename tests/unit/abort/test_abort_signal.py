"""Verify AbortController + AbortSignal."""

from __future__ import annotations

import threading

import pytest

from eden.abort import AbortController, AbortSignal
from eden.errors import Aborted

pytestmark = pytest.mark.unit


def test_signal_is_initially_clear() -> None:
    ctrl = AbortController()
    assert ctrl.signal.is_aborted() is False


def test_abort_sets_signal() -> None:
    ctrl = AbortController()
    ctrl.abort(reason="user")
    assert ctrl.signal.is_aborted() is True
    assert ctrl.signal.reason == "user"


def test_abort_is_idempotent() -> None:
    ctrl = AbortController()
    ctrl.abort(reason="first")
    ctrl.abort(reason="second")
    assert ctrl.signal.reason == "first"


def test_signal_raise_if_aborted_raises() -> None:
    ctrl = AbortController()
    ctrl.abort(reason="x")
    with pytest.raises(Aborted) as excinfo:
        ctrl.signal.raise_if_aborted()
    assert excinfo.value.reason == "x"


def test_signal_raise_if_aborted_noop_when_not_aborted() -> None:
    ctrl = AbortController()
    ctrl.signal.raise_if_aborted()


def test_signal_wait_returns_when_aborted() -> None:
    ctrl = AbortController()

    def trigger() -> None:
        ctrl.abort(reason="bg")

    t = threading.Thread(target=trigger)
    t.start()
    triggered = ctrl.signal.wait(timeout=2.0)
    t.join()
    assert triggered is True


def test_signal_wait_returns_false_on_timeout() -> None:
    ctrl = AbortController()
    triggered = ctrl.signal.wait(timeout=0.05)
    assert triggered is False


def test_controller_signal_is_abort_signal_instance() -> None:
    ctrl = AbortController()
    assert isinstance(ctrl.signal, AbortSignal)


def test_concurrent_abort_first_reason_wins() -> None:
    ctrl = AbortController()
    barrier = threading.Barrier(2)

    def trigger(reason: str) -> None:
        barrier.wait()
        ctrl.abort(reason=reason)

    t1 = threading.Thread(target=trigger, args=("A",))
    t2 = threading.Thread(target=trigger, args=("B",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    # Whichever thread won the lock first, exactly one reason must be observable.
    assert ctrl.signal.is_aborted() is True
    assert ctrl.signal.reason in {"A", "B"}
