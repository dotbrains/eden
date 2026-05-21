"""Restore terminal state on abrupt CLI exit.

Background: some agents and Typer prompts hide the cursor (DECTCEM
``\x1b[?25l``) or place stdin into raw / cbreak mode. When the eden CLI
exits via ``sys.exit()`` from a signal handler — or the agent subprocess
is killed mid-iteration — those toggles are not always reverted, leaving
the user's shell with a hidden cursor or in raw mode.

We register an ``atexit`` callback that:

* sends the "show cursor" DECTCEM sequence (``\x1b[?25h``) to stdout, and
* if stdin is a TTY, restores cooked-mode termios (best-effort — failures
  are swallowed, because by the time atexit fires stdin may already be
  closed or detached).

The handler is split into a pure factory ``make_terminal_cleanup_handler``
so it can be unit-tested without touching the real terminal.
"""

from __future__ import annotations

import atexit
import contextlib
import sys
from collections.abc import Callable
from typing import IO, Any, Protocol

SHOW_CURSOR = "\x1b[?25h"


class _Stdin(Protocol):
    def isatty(self) -> bool: ...
    def fileno(self) -> int: ...


def _restore_cooked_mode(stdin: _Stdin) -> None:
    """Drop stdin out of raw / cbreak mode, if possible.

    On non-POSIX platforms or when the termios import / call fails (closed
    fd, not a real TTY, etc.) this is a silent no-op.
    """
    try:
        import termios
        import tty  # noqa: F401 — keep termios paired with tty
    except ImportError:
        return
    with contextlib.suppress(Exception):
        fd = stdin.fileno()
        attrs = termios.tcgetattr(fd)
        # Re-enable canonical (line) input and echo so the user gets a
        # normal shell back after we exit.
        attrs[3] |= termios.ICANON | termios.ECHO  # lflags
        termios.tcsetattr(fd, termios.TCSADRAIN, attrs)


def make_terminal_cleanup_handler(
    stdin: _Stdin,
    stdout: IO[str] | Any,
) -> Callable[[], None]:
    """Build a side-effect-free cleanup callback over injected streams.

    Returned callable is safe to call multiple times.
    """

    def _handler() -> None:
        is_tty = False
        with contextlib.suppress(Exception):
            is_tty = stdin.isatty()
        if is_tty:
            _restore_cooked_mode(stdin)
        with contextlib.suppress(Exception):
            stdout.write(SHOW_CURSOR)
            with contextlib.suppress(Exception):
                stdout.flush()

    return _handler


_REGISTERED = False


def setup_terminal_cleanup() -> None:
    """Register the terminal cleanup handler on process exit (idempotent)."""
    global _REGISTERED
    if _REGISTERED:
        return
    atexit.register(make_terminal_cleanup_handler(sys.stdin, sys.stdout))
    _REGISTERED = True


__all__ = ["SHOW_CURSOR", "make_terminal_cleanup_handler", "setup_terminal_cleanup"]
