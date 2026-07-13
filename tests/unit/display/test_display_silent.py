"""Tests for ``SilentDisplay``."""

from __future__ import annotations

import pytest

from eden import Display, SilentDisplay
from eden.display._types import (
    IntroEntry,
    SpinnerEntry,
    StatusEntry,
    SummaryEntry,
    TaskLogEntry,
    TextChunkEntry,
    TextEntry,
    ToolCallEntry,
)

pytestmark = pytest.mark.unit


def test_silent_satisfies_protocol() -> None:
    sink: Display = SilentDisplay()
    assert sink is not None


def test_silent_records_intro_and_status() -> None:
    sink = SilentDisplay()
    sink.intro("Run xyz")
    sink.status("starting", severity="info")
    sink.status("oops", severity="error")
    assert sink.entries == [
        IntroEntry(title="Run xyz"),
        StatusEntry(message="starting", severity="info"),
        StatusEntry(message="oops", severity="error"),
    ]


def test_silent_records_text_tool_call_summary() -> None:
    sink = SilentDisplay()
    sink.text("hello")
    sink.text_chunk(" streamed")
    sink.tool_call("Bash", "ls -la")
    sink.summary("Run done", {"branch": "main", "duration": "5s"})
    assert isinstance(sink.entries[0], TextEntry)
    assert isinstance(sink.entries[1], TextChunkEntry)
    assert isinstance(sink.entries[2], ToolCallEntry)
    summary = sink.entries[3]
    assert isinstance(summary, SummaryEntry)
    assert summary.title == "Run done"
    assert summary.rows == {"branch": "main", "duration": "5s"}


def test_silent_spinner_records_entry() -> None:
    sink = SilentDisplay()
    with sink.spinner("loading"):
        pass
    assert sink.entries == [SpinnerEntry(message="loading")]


def test_silent_task_log_collects_messages() -> None:
    sink = SilentDisplay()
    with sink.task_log("compile") as msg:
        msg("step 1")
        msg("step 2")
    assert sink.entries == [TaskLogEntry(title="compile", messages=("step 1", "step 2"))]


def test_silent_reset_clears_entries() -> None:
    sink = SilentDisplay()
    sink.text("a")
    sink.text("b")
    sink.reset()
    assert sink.entries == []
