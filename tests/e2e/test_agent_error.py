"""E2E: agent process exits non-zero without completion → ``AgentError``.

Drives ``eden.run()`` end-to-end with a ``cli_agent`` whose subprocess prints
a Codex-style ``{"type":"error",...}`` event on stdout and then exits with a
non-zero code. Verifies the orchestrator surfaces the failure as a typed
``AgentError`` instead of waiting for the idle timeout.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

import eden
from eden.agents._context import IterationContext
from eden.agents.cli import cli_agent
from eden.sandboxes.no_sandbox import provider as no_sandbox

pytestmark = pytest.mark.e2e


def _failing_agent_argv(stdout_payload: str, exit_code: int) -> list[str]:
    """Return a python ``-c`` argv that prints ``stdout_payload`` then exits."""
    script = (
        "import sys\n"
        f"sys.stdout.write({stdout_payload!r})\n"
        "sys.stdout.flush()\n"
        f"sys.exit({exit_code})\n"
    )
    return [sys.executable, "-c", script]


def test_agent_error_raised_with_parsed_stdout(e2e_git_repo: Path) -> None:
    """Codex-shape error event on stdout surfaces in ``AgentError.parsed_error``."""
    events: list[eden.StreamEvent] = []

    def _build(ctx: IterationContext) -> list[str]:
        return _failing_agent_argv(
            stdout_payload='{"type":"error","message":"rate limit hit"}\n',
            exit_code=2,
        )

    agent = cli_agent(name="codex-fake", model="x", binary="ignored", build_argv=_build)

    with pytest.raises(eden.AgentError) as excinfo:
        eden.run(
            agent=agent,
            sandbox=no_sandbox(),
            prompt="x",
            max_iterations=1,
            completion_signal="<promise>COMPLETE</promise>",
            idle_timeout=30.0,
            on_event=events.append,
        )

    err = excinfo.value
    assert err.agent_name == "codex-fake"
    assert err.exit_code == 2
    assert err.parsed_error == "rate limit hit"
    assert "rate limit hit" in str(err)
    # Recovery hint emitted as a stream event before the raise.
    text_events = [ev.text for ev in events if ev.type == "text" and ev.text is not None]
    assert any("agent run failed — recovery info" in t for t in text_events)
    assert any("rate limit hit" in t for t in text_events)


def test_agent_error_falls_back_to_stderr_when_stdout_silent(
    e2e_git_repo: Path,
) -> None:
    """When stdout has no error event, ``stderr`` populates the message body."""

    def _build(ctx: IterationContext) -> list[str]:
        script = (
            "import sys\n"
            'sys.stderr.write("connection refused\\n")\n'
            "sys.stderr.flush()\n"
            "sys.exit(3)\n"
        )
        return [sys.executable, "-c", script]

    agent = cli_agent(name="quiet", model="x", binary="ignored", build_argv=_build)

    with pytest.raises(eden.AgentError) as excinfo:
        eden.run(
            agent=agent,
            sandbox=no_sandbox(),
            prompt="x",
            max_iterations=1,
            completion_signal="<promise>COMPLETE</promise>",
            idle_timeout=30.0,
        )

    err = excinfo.value
    assert err.exit_code == 3
    assert err.parsed_error is None
    assert "connection refused" in err.stderr


def test_agent_clean_exit_with_completion_does_not_raise(e2e_git_repo: Path) -> None:
    """Sanity check: an agent that prints completion then exits 0 still works."""

    def _build(ctx: IterationContext) -> list[str]:
        return _failing_agent_argv(
            stdout_payload="<promise>COMPLETE</promise>\n",
            exit_code=0,
        )

    agent = cli_agent(name="clean", model="x", binary="ignored", build_argv=_build)

    result = eden.run(
        agent=agent,
        sandbox=no_sandbox(),
        prompt="x",
        max_iterations=1,
        completion_signal="<promise>COMPLETE</promise>",
        idle_timeout=30.0,
    )
    assert result.completion_signal == "<promise>COMPLETE</promise>"


def test_agent_zero_exit_without_completion_does_not_raise(e2e_git_repo: Path) -> None:
    """Exit code 0 without completion is NOT an error — preserves existing semantics.

    Eden's loop allows agents to EOF cleanly without matching the completion
    signal; the iteration just ends with ``completion_signal=None`` and the
    loop moves on. Only non-zero exit codes trigger ``AgentError``.
    """

    def _build(ctx: IterationContext) -> list[str]:
        return _failing_agent_argv(
            stdout_payload="just some output\n",
            exit_code=0,
        )

    agent = cli_agent(name="silent-success", model="x", binary="ignored", build_argv=_build)

    result = eden.run(
        agent=agent,
        sandbox=no_sandbox(),
        prompt="x",
        max_iterations=1,
        completion_signal="<promise>COMPLETE</promise>",
        idle_timeout=30.0,
    )
    assert result.completion_signal is None
    assert result.iterations[0].completion_signal is None
