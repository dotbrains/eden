"""E2E: ``Logging(verbose=True)`` surfaces raw stdout lines as ``raw`` events.

Drives ``eden.run()`` with an agent that prints a JSON-ish line the default
parser would not turn into a ``text`` event, and asserts the literal line is
forwarded through ``on_agent_stream_event`` as a ``raw`` event only when
verbose is enabled.
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


def _agent_argv() -> list[str]:
    script = (
        "import sys\n"
        "sys.stdout.write('hello-line\\n')\n"
        "sys.stdout.write('<promise>COMPLETE</promise>\\n')\n"
        "sys.stdout.flush()\n"
    )
    return [sys.executable, "-c", script]


def _run(verbose: bool, e2e_git_repo: Path) -> list[eden.StreamEvent]:
    seen: list[eden.StreamEvent] = []

    def _build(ctx: IterationContext) -> list[str]:
        return _agent_argv()

    agent = cli_agent(name="raw-fake", model="x", binary="ignored", build_argv=_build)
    eden.run(
        agent=agent,
        sandbox=no_sandbox(),
        prompt="x",
        max_iterations=1,
        completion_signal="<promise>COMPLETE</promise>",
        idle_timeout=30.0,
        logging=eden.Logging.stdout(on_agent_stream_event=seen.append, verbose=verbose),
    )
    return seen


def test_verbose_forwards_raw_events(e2e_git_repo: Path) -> None:
    seen = _run(verbose=True, e2e_git_repo=e2e_git_repo)
    raw = [e for e in seen if e.type == "raw"]
    assert any(e.text == "hello-line" for e in raw)


def test_no_raw_events_without_verbose(e2e_git_repo: Path) -> None:
    seen = _run(verbose=False, e2e_git_repo=e2e_git_repo)
    assert [e for e in seen if e.type == "raw"] == []
