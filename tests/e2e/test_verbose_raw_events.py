"""E2E: ``Logging(verbose=True)`` surfaces raw stdout lines as ``raw`` events.

Drives ``eden.run()`` with an agent that prints a JSON-ish line the default
parser would not turn into a ``text`` event, and asserts the literal line is
forwarded through ``on_agent_stream_event`` as a ``raw`` event only when
verbose is enabled.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest

import eden
from eden.agents._context import IterationContext
from eden.agents.cli import cli_agent
from eden.sandboxes.no_sandbox import provider as no_sandbox
from eden.streaming import StreamEvent

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


@dataclass(frozen=True)
class _StructuredRawAgent:
    name: str = "structured-raw"
    model: str = "x"
    structured_stream: bool = True

    def build_command(self, _ctx: IterationContext) -> list[str]:
        script = (
            "import sys\n"
            'sys.stdout.write(\'{"type":"heartbeat"}\\n\')\n'
            'sys.stdout.write(\'{"type":"message","text":"hello"}\\n\')\n'
            "sys.stdout.write('<promise>COMPLETE</promise>\\n')\n"
            "sys.stdout.flush()\n"
        )
        return [sys.executable, "-u", "-c", script]

    def parse_stream(self, line: str) -> StreamEvent | None:
        if line.startswith('{"type":"message"'):
            return StreamEvent(
                type="text",
                agent_name=self.name,
                iteration=0,
                timestamp=datetime.now(UTC),
                text="hello",
            )
        return None


def test_verbose_file_log_includes_ignored_raw_lines(e2e_git_repo: Path) -> None:
    log_path = e2e_git_repo / "verbose.log"

    eden.run(
        agent=_StructuredRawAgent(),
        sandbox=no_sandbox(),
        prompt="x",
        max_iterations=1,
        completion_signal="<promise>COMPLETE</promise>",
        idle_timeout=30.0,
        logging=eden.Logging.file(log_path, verbose=True),
    )

    log = log_path.read_text(encoding="utf-8")
    assert 'raw: {"type":"heartbeat"}' in log
    assert "text: hello" in log


def test_non_verbose_file_log_omits_ignored_raw_lines(e2e_git_repo: Path) -> None:
    log_path = e2e_git_repo / "quiet.log"

    eden.run(
        agent=_StructuredRawAgent(),
        sandbox=no_sandbox(),
        prompt="x",
        max_iterations=1,
        completion_signal="<promise>COMPLETE</promise>",
        idle_timeout=30.0,
        logging=eden.Logging.file(log_path, verbose=False),
    )

    log = log_path.read_text(encoding="utf-8")
    assert '{"type":"heartbeat"}' not in log
    assert "text: hello" in log
