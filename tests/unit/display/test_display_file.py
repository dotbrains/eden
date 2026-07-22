"""Tests for ``FileDisplay``."""

from __future__ import annotations

from pathlib import Path

import pytest

from eden import FileDisplay

pytestmark = pytest.mark.unit


def test_file_display_appends_text(tmp_path: Path) -> None:
    log = tmp_path / "out" / "run.log"
    sink = FileDisplay(log)
    sink.text("hello")
    sink.text("world")
    content = log.read_text()
    assert "hello" in content
    assert "world" in content
    assert "Run started" in content


def test_file_display_appends_text_chunks_without_newlines(tmp_path: Path) -> None:
    log = tmp_path / "run.log"
    sink = FileDisplay(log)
    sink.text_chunk("Now I have")
    sink.text_chunk(" a clear picture.")
    content = log.read_text()
    assert "Now I have a clear picture." in content
    assert "Now I have\n a clear picture." not in content


def test_file_display_line_entries_start_after_partial_chunk(tmp_path: Path) -> None:
    log = tmp_path / "run.log"
    sink = FileDisplay(log)
    sink.text_chunk("partial agent output")
    sink.tool_call("Read", "file.py")
    assert "partial agent output\nRead(file.py)\n" in log.read_text()


def test_file_display_preserves_chunk_newline_before_line_entries(tmp_path: Path) -> None:
    log = tmp_path / "run.log"
    sink = FileDisplay(log)
    sink.text_chunk("agent output\n")
    sink.status("done")
    assert "agent output\ndone\n" in log.read_text()


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


def test_file_display_status_strips_bracketed_prefix(tmp_path: Path) -> None:
    log = tmp_path / "run.log"
    sink = FileDisplay(log)
    sink.status("[eden] finalized: copied changes")
    content = log.read_text()
    assert "[eden]" not in content
    assert "finalized: copied changes" in content


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
