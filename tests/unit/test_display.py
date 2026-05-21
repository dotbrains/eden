"""Tests for the Display abstraction."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from eden import Display, FileDisplay, RichDisplay, SilentDisplay
from eden.display._types import (
    IntroEntry,
    SpinnerEntry,
    StatusEntry,
    SummaryEntry,
    TaskLogEntry,
    TextEntry,
    ToolCallEntry,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# SilentDisplay
# ---------------------------------------------------------------------------


def test_silent_satisfies_protocol() -> None:
    sink: Display = SilentDisplay()
    assert sink is not None


def test_silent_records_intro_and_status() -> None:
    s = SilentDisplay()
    s.intro("Run xyz")
    s.status("starting", severity="info")
    s.status("oops", severity="error")
    assert s.entries == [
        IntroEntry(title="Run xyz"),
        StatusEntry(message="starting", severity="info"),
        StatusEntry(message="oops", severity="error"),
    ]


def test_silent_records_text_tool_call_summary() -> None:
    s = SilentDisplay()
    s.text("hello")
    s.tool_call("Bash", "ls -la")
    s.summary("Run done", {"branch": "main", "duration": "5s"})
    assert isinstance(s.entries[0], TextEntry)
    assert isinstance(s.entries[1], ToolCallEntry)
    summary = s.entries[2]
    assert isinstance(summary, SummaryEntry)
    assert summary.title == "Run done"
    assert summary.rows == {"branch": "main", "duration": "5s"}


def test_silent_spinner_records_entry() -> None:
    s = SilentDisplay()
    with s.spinner("loading"):
        pass
    assert s.entries == [SpinnerEntry(message="loading")]


def test_silent_task_log_collects_messages() -> None:
    s = SilentDisplay()
    with s.task_log("compile") as msg:
        msg("step 1")
        msg("step 2")
    assert s.entries == [TaskLogEntry(title="compile", messages=("step 1", "step 2"))]


def test_silent_reset_clears_entries() -> None:
    s = SilentDisplay()
    s.text("a")
    s.text("b")
    s.reset()
    assert s.entries == []


# ---------------------------------------------------------------------------
# FileDisplay
# ---------------------------------------------------------------------------


def test_file_display_appends_text(tmp_path: Path) -> None:
    log = tmp_path / "out" / "run.log"
    sink = FileDisplay(log)
    sink.text("hello")
    sink.text("world")
    content = log.read_text()
    assert "hello" in content
    assert "world" in content
    assert "Run started" in content  # delimiter


def test_file_display_records_summary(tmp_path: Path) -> None:
    log = tmp_path / "run.log"
    sink = FileDisplay(log)
    sink.summary("Done", {"branch": "main"})
    content = log.read_text()
    assert "Done" in content
    assert "branch: main" in content


def test_file_display_status_writes_message(tmp_path: Path) -> None:
    log = tmp_path / "run.log"
    sink = FileDisplay(log)
    sink.status("starting", severity="info")
    sink.status("failed", severity="error")
    content = log.read_text()
    assert "starting" in content
    assert "failed" in content


def test_file_display_tool_call_formats(tmp_path: Path) -> None:
    log = tmp_path / "run.log"
    sink = FileDisplay(log)
    sink.tool_call("Read", "/tmp/foo.txt")
    assert "Read(/tmp/foo.txt)" in log.read_text()


def test_file_display_spinner_records_duration(tmp_path: Path) -> None:
    log = tmp_path / "run.log"
    sink = FileDisplay(log)
    with sink.spinner("step"):
        pass
    content = log.read_text()
    assert "step..." in content
    assert "step done" in content


def test_file_display_task_log_emits_collected_messages(tmp_path: Path) -> None:
    log = tmp_path / "run.log"
    sink = FileDisplay(log)
    with sink.task_log("title") as msg:
        msg("a")
        msg("b")
    content = log.read_text()
    assert "title" in content
    assert "  a" in content
    assert "  b" in content
    assert "done" in content


def test_file_display_task_log_emits_on_failure(tmp_path: Path) -> None:
    log = tmp_path / "run.log"
    sink = FileDisplay(log)
    with pytest.raises(ValueError):
        with sink.task_log("title") as msg:
            msg("a")
            raise ValueError("boom")
    content = log.read_text()
    assert "title failed" in content


def test_file_display_creates_parent_dir(tmp_path: Path) -> None:
    log = tmp_path / "a" / "b" / "c" / "run.log"
    sink = FileDisplay(log)
    assert log.parent.exists()
    sink.text("ok")
    assert log.exists()


def test_file_display_intro_is_noop(tmp_path: Path) -> None:
    log = tmp_path / "run.log"
    sink = FileDisplay(log)
    size_before = log.stat().st_size
    sink.intro("Hello")
    size_after = log.stat().st_size
    assert size_after == size_before


# ---------------------------------------------------------------------------
# RichDisplay
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------


def test_top_level_display_exports() -> None:
    """All three sinks plus the Display protocol are top-level imports."""
    from eden import Display, FileDisplay, RichDisplay, SilentDisplay

    assert Display is not None
    assert SilentDisplay is not None
    assert FileDisplay is not None
    assert RichDisplay is not None
