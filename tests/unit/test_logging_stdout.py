"""Verify Logging.stdout() and StdoutLogSink."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from eden.errors import InvalidOptions
from eden.logging import Logging
from eden.logging._stdout import StdoutLogSink
from eden.streaming import StreamEvent

pytestmark = pytest.mark.unit


def _ts() -> datetime:
    return datetime(2026, 5, 1, 12, 0, 0, tzinfo=UTC)


def _ev(text: str) -> StreamEvent:
    return StreamEvent(
        type="text",
        agent_name="sim",
        iteration=0,
        timestamp=_ts(),
        text=text,
    )


def test_logging_stdout_factory() -> None:
    cfg = Logging.stdout()
    assert cfg.type == "stdout"
    assert cfg.path is None
    assert cfg.level == "info"


def test_logging_stdout_factory_with_level() -> None:
    cfg = Logging.stdout(level="debug")
    assert cfg.level == "debug"


def test_logging_file_without_path_rejected() -> None:
    with pytest.raises(InvalidOptions):
        Logging(type="file", path=None)


def test_logging_stdout_with_path_rejected() -> None:
    with pytest.raises(InvalidOptions):
        Logging(type="stdout", path=Path("x.log"))


def test_logging_unknown_type_rejected() -> None:
    with pytest.raises(InvalidOptions):
        Logging(type="syslog")  # type: ignore[arg-type]


def test_stdout_sink_writes_redacted_text(capsys: pytest.CaptureFixture[str]) -> None:
    sink = StdoutLogSink(level="info", env_values=("mySecret",))
    try:
        sink.write(_ev("password=mySecret here"))
    finally:
        sink.close()
    out = capsys.readouterr().out
    assert "password=" in out
    assert "mySecret" not in out


def test_stdout_sink_ignores_writes_after_close(capsys: pytest.CaptureFixture[str]) -> None:
    sink = StdoutLogSink(level="info", env_values=())
    sink.close()
    sink.write(_ev("late line"))
    assert "late line" not in capsys.readouterr().out
