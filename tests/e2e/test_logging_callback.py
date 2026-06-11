"""E2E: Logging.on_agent_stream_event fires for agent-derived events only."""

from __future__ import annotations

from pathlib import Path

import pytest

import eden
from eden.sandboxes.no_sandbox import provider as no_sandbox

pytestmark = pytest.mark.e2e


def test_callback_receives_agent_text_only(e2e_git_repo: Path) -> None:
    captured: list[eden.StreamEvent] = []
    log_path = e2e_git_repo / "out.log"
    eden.run(
        agent=eden.simulated_agent(
            output="line one\nline two\n<promise>COMPLETE</promise>\n",
            delay_per_line=0.5,
        ),
        sandbox=no_sandbox(),
        prompt="x",
        max_iterations=1,
        idle_timeout=10.0,
        idle_warning_interval=0.05,  # fire some warnings
        logging=eden.Logging.file(
            path=log_path,
            on_agent_stream_event=captured.append,
        ),
    )
    types = {ev.type for ev in captured}
    # Agent emits text events; callback never receives idle_warning.
    assert "text" in types
    assert "idle_warning" not in types
    # Eden's own context-window text event is emitted *outside* the agent stream
    # forwarder, so it must not appear here.
    assert not any(
        ev.type == "text" and ev.text and ev.text.startswith("Context window:") for ev in captured
    )


def test_callback_errors_swallowed(e2e_git_repo: Path) -> None:
    def raises(_ev: eden.StreamEvent) -> None:
        raise RuntimeError("boom")

    # Run completes without surfacing the callback exception.
    result = eden.run(
        agent=eden.simulated_agent(output="hello\n<promise>COMPLETE</promise>\n"),
        sandbox=no_sandbox(),
        prompt="x",
        max_iterations=1,
        logging=eden.Logging.file(
            path=e2e_git_repo / "out.log",
            on_agent_stream_event=raises,
        ),
    )
    assert result.completion_signal == "<promise>COMPLETE</promise>"


def test_no_callback_keeps_run_unchanged(e2e_git_repo: Path) -> None:
    result = eden.run(
        agent=eden.simulated_agent(output="hi\n<promise>COMPLETE</promise>\n"),
        sandbox=no_sandbox(),
        prompt="x",
        max_iterations=1,
        logging=eden.Logging.file(path=e2e_git_repo / "out.log"),
    )
    assert result.completion_signal == "<promise>COMPLETE</promise>"


def test_stdout_sink_logs_to_stdout(e2e_git_repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    result = eden.run(
        agent=eden.simulated_agent(output="stdout sink line\n<promise>COMPLETE</promise>\n"),
        sandbox=no_sandbox(),
        prompt="x",
        max_iterations=1,
        logging=eden.Logging.stdout(),
    )
    assert result.completion_signal == "<promise>COMPLETE</promise>"
    assert result.log_file_path is None
    assert "stdout sink line" in capsys.readouterr().out
