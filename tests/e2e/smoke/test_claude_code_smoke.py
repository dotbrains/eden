"""Smoke E2E: claude_code agent + no_sandbox + session capture."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

import eden
from tests._fake_claude import Transcript, install_fake_claude

pytestmark = pytest.mark.e2e


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="fake-claude shim relies on POSIX-style executable PATH lookup",
)
def test_claude_code_full_run(
    e2e_git_repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transcript = (
        Transcript()
        .system_init()
        .text("working on it")
        .tool("Read", {"path": "/workspace/src/x.py"})
        .text("<promise>COMPLETE</promise>")
        .result(session_id="test-session-abc", input_tokens=12, output_tokens=34)
    )
    install_fake_claude(
        tmp_dir=tmp_path / "fake_claude",
        transcript=transcript,
        session_id="test-session-abc",
        sandbox_cwd=str(e2e_git_repo),  # no_sandbox: sandbox_cwd == host_repo_path
        monkeypatch=monkeypatch,
    )

    events: list[eden.StreamEvent] = []
    result = eden.run(
        agent=eden.claude_code(model="test-model"),
        sandbox=__import__(
            "eden.sandboxes.no_sandbox",
            fromlist=["provider"],
        ).provider(),
        prompt="please complete the task",
        max_iterations=1,
        completion_signal="<promise>COMPLETE</promise>",
        idle_timeout=10.0,
        on_event=events.append,
    )

    # Completion fired
    assert result.completion_signal == "<promise>COMPLETE</promise>"

    # Session metadata populated from the result line
    assert result.session_id == "test-session-abc"
    assert result.usage is not None
    assert result.usage.input_tokens == 12
    assert result.usage.output_tokens == 34
    assert result.iterations[0].session_id == "test-session-abc"
    assert result.iterations[0].usage is not None

    # Session file copied + path-rewritten
    assert result.session_file_path is not None
    assert result.session_file_path.exists()
    assert result.session_file_path.parent == e2e_git_repo / ".eden" / "sessions" / "main"
    assert result.session_file_path.name == "iter-0-test-session-abc.jsonl"
    body_lines = [
        json.loads(line)
        for line in result.session_file_path.read_text(encoding="utf-8").strip().split("\n")
    ]
    # The shim wrote {"cwd": "<sandbox_cwd>"} and
    # {"tool_input": {"file_path": "<sandbox_cwd>/src/x.py"}};
    # in no_sandbox sandbox_cwd == host_repo_path so paths match either way.
    assert body_lines[0] == {"cwd": str(e2e_git_repo)}

    # tool_call event landed
    tool_calls = [e for e in events if e.type == "tool_call"]
    assert len(tool_calls) >= 1
    assert tool_calls[0].tool_name == "Read"

    # usage event landed (final)
    usage_events = [e for e in events if e.type == "usage"]
    assert len(usage_events) == 1
    assert usage_events[0].session_id == "test-session-abc"


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="fake-claude shim relies on POSIX-style executable PATH lookup",
)
def test_claude_code_capture_sessions_false(
    e2e_git_repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transcript = (
        Transcript()
        .text("ok")
        .text("<promise>COMPLETE</promise>")
        .result(session_id="no-capture-id", input_tokens=1, output_tokens=2)
    )
    install_fake_claude(
        tmp_dir=tmp_path / "fake_claude",
        transcript=transcript,
        session_id="no-capture-id",
        sandbox_cwd=str(e2e_git_repo),
        monkeypatch=monkeypatch,
    )

    result = eden.run(
        agent=eden.claude_code(model="test-model", capture_sessions=False),
        sandbox=__import__(
            "eden.sandboxes.no_sandbox",
            fromlist=["provider"],
        ).provider(),
        prompt="x",
        max_iterations=1,
        completion_signal="<promise>COMPLETE</promise>",
        idle_timeout=10.0,
    )

    assert result.session_id == "no-capture-id"  # populated from stream
    assert result.session_file_path is None  # but no file written
    assert result.usage is not None  # usage still populated
    # No .eden/sessions/ directory created at all
    assert not (e2e_git_repo / ".eden" / "sessions").exists()
