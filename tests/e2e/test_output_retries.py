"""E2E: ``Output(max_retries=...)`` retries failed structured-output runs.

Uses ``simulated_agent`` (no session capture) so the retry takes the
fresh-re-run fallback path. A stateful output callable emits invalid output on
the first call and valid output afterward.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from datetime import UTC, datetime

import pytest

import eden
from eden.agents._context import IterationContext
from eden.agents.simulated import simulated_agent
from eden.errors import StructuredOutputError
from eden.output import Output
from eden.sandboxes.no_sandbox import provider as no_sandbox
from eden.streaming import StreamEvent

pytestmark = pytest.mark.e2e

_PROMPT = "Emit your answer inside <result>...</result>."
_GOOD = '<result>{"ok": true}</result>\n<promise>COMPLETE</promise>\n'
_BAD = "<result>{not valid json</result>\n<promise>COMPLETE</promise>\n"


def _counting_output(
    seq: list[str],
) -> tuple[Callable[[IterationContext], str], dict[str, int]]:
    state = {"n": 0}

    def out(_ctx: IterationContext) -> str:
        i = state["n"]
        state["n"] += 1
        return seq[min(i, len(seq) - 1)]

    return out, state


def test_retry_recovers_after_bad_then_good(e2e_git_repo: object) -> None:
    out_fn, state = _counting_output([_BAD, _GOOD])
    agent = simulated_agent(output=out_fn)

    result = eden.run(
        agent=agent,
        sandbox=no_sandbox(),
        prompt=_PROMPT,
        output=Output.object(tag="result", schema=lambda d: d, max_retries=2),
        idle_timeout=30.0,
    )

    assert result.output == {"ok": True}
    assert state["n"] == 2  # one failure + one successful retry


def test_retries_exhausted_raises(e2e_git_repo: object) -> None:
    out_fn, state = _counting_output([_BAD])  # always bad
    agent = simulated_agent(output=out_fn)

    with pytest.raises(StructuredOutputError):
        eden.run(
            agent=agent,
            sandbox=no_sandbox(),
            prompt=_PROMPT,
            output=Output.object(tag="result", schema=lambda d: d, max_retries=2),
            idle_timeout=30.0,
        )

    assert state["n"] == 3  # initial attempt + 2 retries


class _ResumeRetryAgent:
    """Emits a session id, bad output first, valid output once resumed.

    Lets the retry take the *resume* branch (exc.session_id is populated), as
    opposed to the fresh-re-run fallback the simulated_agent tests exercise.
    """

    name = "rr"
    model = "x"

    def build_command(self, ctx: IterationContext) -> list[str]:
        good = ctx.resume_session is not None
        result = '<result>{"ok": true}</result>' if good else "<result>{bad"
        script = (
            "import sys\n"
            "sys.stdout.write('SID:sess-1\\n')\n"
            f"sys.stdout.write({result!r} + '\\n')\n"
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


def test_retry_uses_resume_when_session_captured(e2e_git_repo: object) -> None:
    # With max_retries=1, success is only possible via the resume branch: the
    # agent emits valid output exclusively when it sees a resume_session, so a
    # fresh re-run would fail again and raise.
    result = eden.run(
        agent=_ResumeRetryAgent(),
        sandbox=no_sandbox(),
        prompt=_PROMPT,
        output=Output.object(tag="result", schema=lambda d: d, max_retries=1),
        idle_timeout=30.0,
    )
    assert result.output == {"ok": True}


def test_no_retry_by_default_raises_immediately(e2e_git_repo: object) -> None:
    out_fn, state = _counting_output([_BAD, _GOOD])
    agent = simulated_agent(output=out_fn)

    with pytest.raises(StructuredOutputError):
        eden.run(
            agent=agent,
            sandbox=no_sandbox(),
            prompt=_PROMPT,
            output=Output.object(tag="result", schema=lambda d: d),  # max_retries=0
            idle_timeout=30.0,
        )

    assert state["n"] == 1  # no retry attempted
