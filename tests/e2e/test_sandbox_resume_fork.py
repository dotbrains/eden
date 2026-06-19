"""E2E: ``Sandbox.resume()`` / ``Sandbox.fork()`` reuse the live sandbox.

These continue the sandbox's most recent session without the caller threading
session ids by hand. A tiny inline agent emits a session id and echoes the
``resume_session`` it was given so the test can assert it was forwarded.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime

import pytest

from eden.agents._context import IterationContext
from eden.errors import InvalidOptions
from eden.sandboxes import create_sandbox
from eden.sandboxes.no_sandbox import provider as no_sandbox
from eden.streaming import StreamEvent

pytestmark = pytest.mark.e2e


class _SessionAgent:
    """Emits a fixed session id and echoes the resume id it was launched with."""

    name = "sess"
    model = "x"

    def build_command(self, ctx: IterationContext) -> list[str]:
        rs = ctx.resume_session or "none"
        script = (
            "import sys\n"
            "sys.stdout.write('SID:abc-123\\n')\n"
            f"sys.stdout.write('RESUMED:{rs}\\n')\n"
            "sys.stdout.write('<promise>COMPLETE</promise>\\n')\n"
        )
        return [sys.executable, "-c", script]

    def parse_stream(self, line: str) -> StreamEvent | None:
        if line.startswith("SID:"):
            return StreamEvent(
                type="session_id",
                agent_name=self.name,
                iteration=0,
                timestamp=datetime.now(UTC),
                session_id=line[len("SID:") :],
            )
        return None


def test_resume_reuses_last_session(e2e_git_repo: object) -> None:
    with create_sandbox(sandbox=no_sandbox()) as sb:
        agent = _SessionAgent()
        r1 = sb.run(agent=agent, prompt="first", idle_timeout=30.0)
        assert r1.session_id == "abc-123"
        assert "RESUMED:none" in r1.stdout

        r2 = sb.resume("second", agent=agent, idle_timeout=30.0)
        # resume() forwarded the captured session id into the rerun.
        assert "RESUMED:abc-123" in r2.stdout


def test_fork_reuses_last_session(e2e_git_repo: object) -> None:
    with create_sandbox(sandbox=no_sandbox()) as sb:
        agent = _SessionAgent()
        sb.run(agent=agent, prompt="first", idle_timeout=30.0)
        r2 = sb.fork("branch", agent=agent, idle_timeout=30.0)
        assert "RESUMED:abc-123" in r2.stdout


def test_resume_without_prior_session_raises(e2e_git_repo: object) -> None:
    with create_sandbox(sandbox=no_sandbox()) as sb:
        with pytest.raises(InvalidOptions, match="no captured session"):
            sb.resume("x", agent=_SessionAgent())


def test_fork_without_resume_session_raises(e2e_git_repo: object) -> None:
    with create_sandbox(sandbox=no_sandbox()) as sb:
        with pytest.raises(InvalidOptions, match="fork_session=True requires"):
            sb.run(agent=_SessionAgent(), prompt="x", fork_session=True, idle_timeout=30.0)
