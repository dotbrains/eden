"""Smoke E2E: simulated_agent + no_sandbox + merge_to_head + idle warnings."""

from __future__ import annotations

from pathlib import Path

import pytest

import eden

pytestmark = pytest.mark.e2e


def test_simulated_agent_full_run(e2e_git_repo: Path) -> None:
    events: list[eden.StreamEvent] = []
    result = eden.run(
        agent=eden.simulated_agent(
            output="working on it\n<promise>COMPLETE</promise>\n",
            delay_per_line=0.15,
        ),
        sandbox=__import__(
            "eden.sandboxes.no_sandbox",
            fromlist=["provider"],
        ).provider(),
        prompt="branch={{SOURCE_BRANCH}} target={{TARGET_BRANCH}}",
        max_iterations=1,
        completion_signal="<promise>COMPLETE</promise>",
        idle_timeout=10.0,
        idle_warning_interval=0.05,  # fire warnings during run
        on_event=events.append,
    )

    assert result.completion_signal == "<promise>COMPLETE</promise>"
    assert len(result.iterations) == 1
    assert result.iterations[0].completion_signal == "<promise>COMPLETE</promise>"
    assert "working on it" in result.stdout
    # rendered prompt has substituted SOURCE_BRANCH and TARGET_BRANCH
    assert "branch=" in result.prompt
    assert "target=main" in result.prompt
    assert "{{SOURCE_BRANCH}}" not in result.prompt
    # log file written and discoverable
    assert result.log_file_path is not None
    assert result.log_file_path.exists()
    body = result.log_file_path.read_text()
    assert "working on it" in body
    # at least one idle_warning event fired through on_event
    assert any(ev.type == "idle_warning" for ev in events)
    # text events for the agent's output
    text_events = [ev for ev in events if ev.type == "text"]
    assert any(ev.text == "working on it" for ev in text_events)


def test_max_iterations_no_completion(e2e_git_repo: Path) -> None:
    result = eden.run(
        agent=eden.simulated_agent(output="just text\n"),
        sandbox=__import__("eden.sandboxes.no_sandbox", fromlist=["provider"]).provider(),
        prompt="x",
        max_iterations=3,
        completion_signal="NEVER_HIT",
        idle_timeout=10.0,
    )
    assert len(result.iterations) == 3
    assert result.completion_signal is None
    assert all(it.completion_signal is None for it in result.iterations)
