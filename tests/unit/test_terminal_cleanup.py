"""Tests for eden.cli._terminal_cleanup."""

from __future__ import annotations

import io

from eden.cli._terminal_cleanup import (
    SHOW_CURSOR,
    make_terminal_cleanup_handler,
)


class _FakeTtyStdin:
    def __init__(self, *, tty: bool = True) -> None:
        self._tty = tty
        # fileno() of a real fd that isn't actually a TTY — termios will
        # raise, which the handler must swallow.
        self._fd = -1  # invalid fd; termios.tcgetattr will fail

    def isatty(self) -> bool:
        return self._tty

    def fileno(self) -> int:
        return self._fd


def test_handler_writes_show_cursor_on_tty() -> None:
    stdin = _FakeTtyStdin(tty=True)
    stdout = io.StringIO()

    make_terminal_cleanup_handler(stdin, stdout)()

    assert SHOW_CURSOR in stdout.getvalue()


def test_handler_writes_show_cursor_when_not_tty() -> None:
    # Even when stdin is not a TTY, we still want to emit the cursor
    # escape — non-TTY stdouts (logged terminal recorders, asciinema)
    # generally ignore it and TTY stdouts paired with non-TTY stdin
    # benefit from the restore.
    stdin = _FakeTtyStdin(tty=False)
    stdout = io.StringIO()

    make_terminal_cleanup_handler(stdin, stdout)()

    assert stdout.getvalue() == SHOW_CURSOR


def test_handler_is_idempotent() -> None:
    stdin = _FakeTtyStdin(tty=True)
    stdout = io.StringIO()

    handler = make_terminal_cleanup_handler(stdin, stdout)
    handler()
    handler()

    # Two writes — once per call. The handler is not memoized; what we're
    # asserting is that calling twice does not raise.
    assert stdout.getvalue().count(SHOW_CURSOR) == 2


def test_handler_swallows_stdout_write_failures() -> None:
    stdin = _FakeTtyStdin(tty=True)

    class _BrokenStdout:
        def write(self, _data: str) -> int:
            raise OSError("stream closed")

        def flush(self) -> None:  # pragma: no cover — unreachable
            raise OSError("stream closed")

    # Must not raise.
    make_terminal_cleanup_handler(stdin, _BrokenStdout())()


def test_handler_swallows_stdin_isatty_failures() -> None:
    class _BrokenStdin:
        def isatty(self) -> bool:
            raise OSError("stream closed")

        def fileno(self) -> int:  # pragma: no cover — unreachable when isatty raises
            return -1

    stdout = io.StringIO()
    # Must not raise; still emits the cursor sequence.
    make_terminal_cleanup_handler(_BrokenStdin(), stdout)()
    assert stdout.getvalue() == SHOW_CURSOR


def test_setup_terminal_cleanup_is_idempotent() -> None:
    from eden.cli import _terminal_cleanup as mod

    # Reset and re-register; calling twice must not register twice.
    mod._REGISTERED = False
    try:
        mod.setup_terminal_cleanup()
        mod.setup_terminal_cleanup()
        assert mod._REGISTERED is True
    finally:
        # Don't pollute other tests' atexit lists.
        mod._REGISTERED = True
