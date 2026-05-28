"""Process-wide shutdown registry.

Sandboxes need synchronous cleanup (remove a container, release a cloud
workspace) when the host process is killed by ``SIGTERM`` or exits
without running ``try/finally`` blocks. Registering a per-sandbox signal
handler clobbers the user's handlers and leaks one handler per sandbox;
this module installs at most one handler per signal and fans out to a
set of teardown callbacks.

Mirrors sandcastle's ``shutdownRegistry.ts``.

Lifecycle:

* ``SIGINT`` (Ctrl+C) — runs teardowns, then re-raises
  :class:`KeyboardInterrupt`, so caller ``try/finally`` still gets a
  chance to run.
* ``SIGTERM`` — runs teardowns, then calls :func:`sys.exit` with code
  ``143`` (POSIX convention: ``128 + SIGTERM``).
* normal exit — :mod:`atexit` runs teardowns without forcing an exit
  code.

Constraints:

* Teardowns run synchronously; they must not block.
* Callback exceptions are swallowed — one failing teardown must not
  block the others.
* Signal handlers can only be installed on the main thread; when the
  registry is first touched from a worker thread, signal installation
  is skipped and the registry falls back to :mod:`atexit` only.
"""

from __future__ import annotations

import atexit
import signal
import sys
import threading
from collections.abc import Callable
from typing import Any

ShutdownCallback = Callable[[], None]

_lock = threading.Lock()
_callbacks: list[ShutdownCallback] = []
_installed = False
_prev_sigint: Any = None
_prev_sigterm: Any = None


def _run_all() -> None:
    # Snapshot under the lock so concurrent register/unregister can't mutate
    # the iteration; run outside the lock so callbacks can re-enter the
    # registry (e.g. an unregister inside the teardown).
    with _lock:
        snapshot = list(_callbacks)
    for cb in snapshot:
        try:
            cb()
        except Exception:
            pass


def _on_atexit() -> None:
    _run_all()


def _on_sigint(signum: int, frame: Any) -> None:
    _detach()
    _run_all()
    raise KeyboardInterrupt


def _on_sigterm(signum: int, frame: Any) -> None:
    _detach()
    _run_all()
    sys.exit(143)


def _attach() -> None:
    global _installed, _prev_sigint, _prev_sigterm
    if _installed:
        return
    if threading.current_thread() is not threading.main_thread():
        # signal.signal raises ValueError off the main thread; fall back to
        # atexit-only so worker-thread use still gets normal-exit cleanup.
        atexit.register(_on_atexit)
        _installed = True
        return
    try:
        _prev_sigint = signal.signal(signal.SIGINT, _on_sigint)
        _prev_sigterm = signal.signal(signal.SIGTERM, _on_sigterm)
    except (ValueError, OSError):
        _prev_sigint = None
        _prev_sigterm = None
    atexit.register(_on_atexit)
    _installed = True


def _detach() -> None:
    global _installed, _prev_sigint, _prev_sigterm
    if not _installed:
        return
    try:
        if _prev_sigint is not None:
            signal.signal(signal.SIGINT, _prev_sigint)
        if _prev_sigterm is not None:
            signal.signal(signal.SIGTERM, _prev_sigterm)
    except (ValueError, OSError):
        pass
    try:
        atexit.unregister(_on_atexit)
    except Exception:
        pass
    _prev_sigint = None
    _prev_sigterm = None
    _installed = False


def register_shutdown(callback: ShutdownCallback) -> Callable[[], None]:
    """Register ``callback`` to run on ``SIGINT`` / ``SIGTERM`` / exit.

    Returns an idempotent unregister function. The first registration
    installs the shared handlers; the last unregistration removes them
    so default signal behaviour is restored.

    Callbacks must be synchronous. They run in registration order;
    exceptions raised by any one teardown are swallowed and the next
    teardown still runs.
    """
    active = [True]

    with _lock:
        _callbacks.append(callback)
        _attach()

    def _unregister() -> None:
        if not active[0]:
            return
        active[0] = False
        with _lock:
            try:
                _callbacks.remove(callback)
            except ValueError:
                pass
            if not _callbacks:
                _detach()

    return _unregister


__all__ = ["ShutdownCallback", "register_shutdown"]
