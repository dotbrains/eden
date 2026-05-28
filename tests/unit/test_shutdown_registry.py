"""Verify register_shutdown installs handlers once and fans out on shutdown."""

from __future__ import annotations

import os
import signal
import sys
from collections.abc import Iterator

import pytest

from eden.abort._shutdown import (
    _callbacks,
    _detach,
    _on_atexit,
    _on_sigint,
    _on_sigterm,
    register_shutdown,
)

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _reset_registry_state() -> Iterator[None]:
    """Each test starts with an empty registry and detached handlers."""
    _callbacks.clear()
    _detach()
    yield
    _callbacks.clear()
    _detach()


def test_register_then_unregister_is_idempotent() -> None:
    calls: list[str] = []
    unreg = register_shutdown(lambda: calls.append("first"))
    unreg()
    unreg()  # second call is a no-op
    # callback was removed; manually firing atexit must not invoke it.
    _on_atexit()
    assert calls == []


def test_atexit_runs_every_callback_in_order() -> None:
    calls: list[str] = []
    register_shutdown(lambda: calls.append("a"))
    register_shutdown(lambda: calls.append("b"))
    register_shutdown(lambda: calls.append("c"))
    _on_atexit()
    assert calls == ["a", "b", "c"]


def test_callback_exceptions_are_swallowed() -> None:
    """A failing teardown does not block the rest."""
    calls: list[str] = []

    def _bad() -> None:
        raise RuntimeError("boom")

    register_shutdown(lambda: calls.append("a"))
    register_shutdown(_bad)
    register_shutdown(lambda: calls.append("c"))
    _on_atexit()
    assert calls == ["a", "c"]


def test_unregister_after_callback_fired_is_safe() -> None:
    """Calling the returned unregister after shutdown ran is a no-op."""
    unreg = register_shutdown(lambda: None)
    _on_atexit()
    unreg()  # must not raise


def test_sigint_handler_raises_keyboard_interrupt() -> None:
    calls: list[str] = []
    register_shutdown(lambda: calls.append("a"))
    with pytest.raises(KeyboardInterrupt):
        _on_sigint(signal.SIGINT, None)
    assert calls == ["a"]


def test_sigterm_handler_exits_with_143() -> None:
    calls: list[str] = []
    register_shutdown(lambda: calls.append("a"))
    with pytest.raises(SystemExit) as exc_info:
        _on_sigterm(signal.SIGTERM, None)
    assert exc_info.value.code == 143
    assert calls == ["a"]


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals only")
def test_signal_handler_installed_on_first_registration() -> None:
    """SIGINT default handler is replaced after the first registration."""
    default = signal.getsignal(signal.SIGINT)
    unreg = register_shutdown(lambda: None)
    try:
        replaced = signal.getsignal(signal.SIGINT)
        assert replaced is not default
        assert callable(replaced)
    finally:
        unreg()
    # After last unregister, the previous handler is restored.
    assert signal.getsignal(signal.SIGINT) is default


def test_real_sigterm_runs_teardowns(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """End-to-end: spawn a child that registers a teardown writing a sentinel
    file, kill it with SIGTERM, verify the sentinel exists.

    Catches regressions where the registry stops actually wiring signals.
    """
    if sys.platform == "win32":
        pytest.skip("POSIX signals only")
    sentinel = tmp_path / "ran.txt"
    child = tmp_path / "child.py"
    child.write_text(
        "import sys, time\n"
        "sys.path.insert(0, " + repr(str(_repo_root())) + ")\n"
        "from eden.abort import register_shutdown\n"
        "register_shutdown(lambda: open(" + repr(str(sentinel)) + ', "w").write("ok"))\n'
        "print('ready', flush=True)\n"
        "time.sleep(30)\n",
        encoding="utf-8",
    )
    import subprocess

    proc = subprocess.Popen(
        [sys.executable, str(child)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        # Wait until the child prints 'ready' so the handler is installed.
        assert proc.stdout is not None
        line = proc.stdout.readline().decode().strip()
        assert line == "ready"
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=5)
    finally:
        if proc.poll() is None:
            proc.kill()
    assert sentinel.exists(), "shutdown teardown did not run on SIGTERM"
    assert sentinel.read_text(encoding="utf-8") == "ok"


def _repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    # tests/unit/<this>.py → repo root is two dirs up.
    return os.path.dirname(os.path.dirname(here))
