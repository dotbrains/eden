"""RichDisplay output behavior."""

from __future__ import annotations

import io

import pytest

from eden import RichDisplay

pytestmark = pytest.mark.unit


def _capturing_console() -> tuple[object, io.StringIO]:
    """Build a rich console that writes to a StringIO for assertions."""
    from rich.console import Console

    buf = io.StringIO()
    console = Console(
        file=buf,
        force_terminal=False,
        color_system=None,
        width=200,
    )
    return console, buf


def test_rich_display_intro_writes_to_stream() -> None:
    console, buf = _capturing_console()
    sink = RichDisplay(console=console)
    sink.intro("Welcome")
    assert "Welcome" in buf.getvalue()


def test_rich_display_text_writes_to_stream() -> None:
    console, buf = _capturing_console()
    sink = RichDisplay(console=console)
    sink.text("hello world")
    assert "hello world" in buf.getvalue()


def test_rich_display_text_chunk_writes_without_newline() -> None:
    console, buf = _capturing_console()
    sink = RichDisplay(console=console)
    sink.text_chunk("hello")
    sink.text_chunk(" world")
    assert "hello world" in buf.getvalue()
    assert "hello\n world" not in buf.getvalue()


def test_rich_display_status_includes_message() -> None:
    console, buf = _capturing_console()
    sink = RichDisplay(console=console)
    sink.status("starting", severity="info")
    sink.status("done", severity="success")
    sink.status("careful", severity="warn")
    sink.status("oops", severity="error")
    out = buf.getvalue()
    assert "starting" in out
    assert "done" in out
    assert "careful" in out
    assert "oops" in out


def test_rich_display_summary_includes_rows() -> None:
    console, buf = _capturing_console()
    sink = RichDisplay(console=console)
    sink.summary("Run done", {"branch": "main", "duration": "5s"})
    out = buf.getvalue()
    assert "Run done" in out
    assert "branch" in out and "main" in out
    assert "duration" in out and "5s" in out


def test_rich_display_tool_call_writes_name_and_args() -> None:
    console, buf = _capturing_console()
    sink = RichDisplay(console=console)
    sink.tool_call("Bash", "ls -la /tmp")
    out = buf.getvalue()
    assert "Bash" in out
    assert "ls -la /tmp" in out


def test_rich_display_spinner_emits_done_line() -> None:
    console, buf = _capturing_console()
    sink = RichDisplay(console=console)
    with sink.spinner("loading"):
        pass
    out = buf.getvalue()
    assert "loading done" in out


def test_rich_display_task_log_success() -> None:
    console, buf = _capturing_console()
    sink = RichDisplay(console=console)
    with sink.task_log("compile") as msg:
        msg("first step")
        msg("second step")
    out = buf.getvalue()
    assert "compile" in out
    assert "first step" in out
    assert "second step" in out


def test_rich_display_task_log_failure() -> None:
    console, buf = _capturing_console()
    sink = RichDisplay(console=console)
    with pytest.raises(RuntimeError):
        with sink.task_log("compile") as msg:
            msg("step 1")
            raise RuntimeError("boom")
    out = buf.getvalue()
    assert "compile failed" in out
