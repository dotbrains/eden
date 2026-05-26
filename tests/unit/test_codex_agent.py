"""Verify the codex agent factory."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from pathlib import Path

import pytest

from eden.agents import IterationContext
from eden.agents.codex import codex
from eden.providers._types import ExecResult

pytestmark = pytest.mark.unit


class _StubHandle:
    worktree_path = Path("/workspace")

    def exec(
        self,
        cmd: str,
        *,
        on_line: Callable[[str], None] | None = None,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
        stdin: str | None = None,
    ) -> ExecResult:
        return ExecResult(stdout="", stderr="", exit_code=0)

    def copy_file_in(self, host: Path, sandbox: Path) -> None: ...
    def copy_file_out(self, sandbox: Path, host: Path) -> None: ...
    def close(self) -> None: ...


def _ctx(prompt: str = "do work") -> IterationContext:
    return IterationContext(
        iteration=0,
        prompt=prompt,
        sandbox_handle=_StubHandle(),
        worktree_path=Path("/workspace"),
        branch="HEAD",
        name=None,
    )


def test_codex_default_metadata() -> None:
    a = codex()
    assert a.name == "codex"
    assert a.model == "gpt-5"


def test_codex_custom_model() -> None:
    a = codex(model="gpt-4o")
    assert a.model == "gpt-4o"


def test_codex_build_command_shape() -> None:
    """Default invocation: ``codex exec --json --dangerously-bypass-... -m <model>``."""
    a = codex()
    argv = a.build_command(_ctx(prompt="hello"))
    assert argv[:2] == ["codex", "exec"]
    assert "--json" in argv
    assert "--dangerously-bypass-approvals-and-sandbox" in argv
    assert "-m" in argv
    assert argv[argv.index("-m") + 1] == "gpt-5"
    # Prompt is delivered via stdin, not argv.
    assert "hello" not in argv


def test_codex_stdin_carries_prompt() -> None:
    a = codex()
    payload = a.stdin_content(_ctx(prompt="my prompt"))
    assert payload == "my prompt"


def test_codex_extra_args_appended_after_standard_flags() -> None:
    a = codex(extra_args=("--no-cache",))
    argv = a.build_command(_ctx())
    assert "--no-cache" in argv
    assert argv.index("--no-cache") > argv.index("--json")


def test_codex_dangerously_bypass_can_be_disabled() -> None:
    a = codex(dangerously_bypass_approvals_and_sandbox=False)
    argv = a.build_command(_ctx())
    assert "--dangerously-bypass-approvals-and-sandbox" not in argv


def test_codex_effort_unset_omits_override() -> None:
    a = codex()
    argv = a.build_command(_ctx())
    assert "-c" not in argv
    assert not any("model_reasoning_effort" in arg for arg in argv)


def test_codex_effort_threads_config_override() -> None:
    a = codex(effort="high")
    argv = a.build_command(_ctx())
    assert "-c" in argv
    assert 'model_reasoning_effort="high"' in argv


def test_codex_resume_session_adds_resume_subcommand() -> None:
    a = codex()
    ctx = IterationContext(
        iteration=0,
        prompt="continue",
        sandbox_handle=_StubHandle(),
        worktree_path=Path("/workspace"),
        branch="HEAD",
        name=None,
        resume_session="sess-abc",
    )
    argv = a.build_command(ctx)
    assert argv[:4] == ["codex", "exec", "resume", "sess-abc"]


def test_codex_capture_sessions_default_true() -> None:
    a = codex()
    assert a.captures_sessions is True
    assert a.session_storage is not None


def test_codex_capture_sessions_false_clears_storage() -> None:
    a = codex(capture_sessions=False)
    assert a.captures_sessions is False
    assert a.session_storage is None


def test_codex_parse_stream_wired_in() -> None:
    a = codex()
    ev = a.parse_stream(json.dumps({"type": "thread.started", "thread_id": "tid"}))
    assert ev is not None
    assert ev.type == "session_id"
    assert ev.session_id == "tid"
    assert ev.agent_name == "codex"


def test_codex_parse_stream_returns_none_for_unknown() -> None:
    a = codex()
    assert a.parse_stream("garbage") is None
    assert a.parse_stream(json.dumps({"type": "heartbeat"})) is None
