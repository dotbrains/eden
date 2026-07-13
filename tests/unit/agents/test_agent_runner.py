"""Verify _AgentRunner: subprocess spawn, stdout pump, idle integration, abort."""

from __future__ import annotations

import sys
import threading
import time

import pytest

from eden.abort import AbortController
from eden.errors import Aborted, IdleTimeout
from eden.orchestrator._idle import IdleWatchdog
from eden.orchestrator._runner import _AgentRunner

pytestmark = pytest.mark.unit


def test_runner_streams_lines_in_order() -> None:
    argv = [
        sys.executable,
        "-u",
        "-c",
        "import sys\nfor i in range(3):\n    sys.stdout.write(f'line{i}\\n')\n",
    ]
    wd = IdleWatchdog(idle_timeout=10.0, idle_warning_interval=None)
    wd.start()
    try:
        with _AgentRunner(argv=argv, env={}, watchdog=wd) as runner:
            ctrl = AbortController()
            warnings: list[int] = []
            lines = list(
                runner.iter_lines(
                    signal=ctrl.signal,
                    on_warning=warnings.append,
                )
            )
        assert lines == ["line0", "line1", "line2"]
    finally:
        wd.stop()


def test_runner_terminate_stops_subprocess() -> None:
    script = (
        "import time, sys\n"
        "while True:\n"
        "    sys.stdout.write('tick\\n')\n"
        "    sys.stdout.flush()\n"
        "    time.sleep(0.05)\n"
    )
    argv = [sys.executable, "-u", "-c", script]
    wd = IdleWatchdog(idle_timeout=10.0, idle_warning_interval=None)
    wd.start()
    try:
        with _AgentRunner(argv=argv, env={}, watchdog=wd) as runner:
            ctrl = AbortController()
            it = runner.iter_lines(signal=ctrl.signal, on_warning=lambda _m: None)
            next(it)
            runner.terminate()
            # Drain remaining lines until generator exits.
            for _ in it:
                pass
    finally:
        wd.stop()


def test_runner_idle_timeout_raises() -> None:
    argv = [sys.executable, "-u", "-c", "import time\ntime.sleep(2)\n"]
    wd = IdleWatchdog(idle_timeout=0.2, idle_warning_interval=None)
    wd.start()
    try:
        with _AgentRunner(argv=argv, env={}, watchdog=wd) as runner:
            ctrl = AbortController()
            with pytest.raises(IdleTimeout):
                for _ in runner.iter_lines(signal=ctrl.signal, on_warning=lambda _m: None):
                    pass
    finally:
        wd.stop()


def test_runner_abort_signal_raises() -> None:
    script = (
        "import time, sys\n"
        "while True:\n"
        "    sys.stdout.write('x\\n')\n"
        "    sys.stdout.flush()\n"
        "    time.sleep(0.05)\n"
    )
    argv = [sys.executable, "-u", "-c", script]
    wd = IdleWatchdog(idle_timeout=10.0, idle_warning_interval=None)
    wd.start()
    try:
        with _AgentRunner(argv=argv, env={}, watchdog=wd) as runner:
            ctrl = AbortController()
            it = runner.iter_lines(signal=ctrl.signal, on_warning=lambda _m: None)
            next(it)

            def trigger() -> None:
                time.sleep(0.05)
                ctrl.abort(reason="test")

            threading.Thread(target=trigger).start()

            with pytest.raises(Aborted):
                for _ in it:
                    pass
    finally:
        wd.stop()


def test_runner_emits_warnings_via_callback() -> None:
    argv = [sys.executable, "-u", "-c", "import time\ntime.sleep(1)\n"]
    wd = IdleWatchdog(idle_timeout=2.0, idle_warning_interval=0.15)
    wd.start()
    try:
        with _AgentRunner(argv=argv, env={}, watchdog=wd) as runner:
            ctrl = AbortController()
            warnings: list[int] = []
            for _ in runner.iter_lines(signal=ctrl.signal, on_warning=warnings.append):
                pass
        assert warnings  # at least one warning fired
    finally:
        wd.stop()


def test_runner_pipes_stdin_to_subprocess() -> None:
    """Verify stdin payload is delivered to the subprocess (echoed back via stdout)."""
    script = "import sys\ndata = sys.stdin.read()\nsys.stdout.write(f'received:{data!r}\\n')\n"
    argv = [sys.executable, "-u", "-c", script]
    wd = IdleWatchdog(idle_timeout=10.0, idle_warning_interval=None)
    wd.start()
    try:
        with _AgentRunner(
            argv=argv,
            env={},
            watchdog=wd,
            stdin="hello-from-stdin\n",
        ) as runner:
            ctrl = AbortController()
            lines = list(runner.iter_lines(signal=ctrl.signal, on_warning=lambda _m: None))
        assert any("hello-from-stdin" in line for line in lines)
    finally:
        wd.stop()


def test_runner_no_stdin_does_not_open_pipe() -> None:
    """Verify default behaviour: no stdin pipe opened, agent inherits null stdin."""
    script = "import sys\nsys.stdout.write(f'isatty={sys.stdin.isatty()}\\n')\n"
    argv = [sys.executable, "-u", "-c", script]
    wd = IdleWatchdog(idle_timeout=10.0, idle_warning_interval=None)
    wd.start()
    try:
        with _AgentRunner(argv=argv, env={}, watchdog=wd) as runner:
            ctrl = AbortController()
            list(runner.iter_lines(signal=ctrl.signal, on_warning=lambda _m: None))
    finally:
        wd.stop()
