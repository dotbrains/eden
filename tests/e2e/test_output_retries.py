"""E2E: ``Output(max_retries=...)`` retries failed structured-output runs.

Uses ``simulated_agent`` (no session capture) so the retry takes the
fresh-re-run fallback path. A stateful output callable emits invalid output on
the first call and valid output afterward.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

import eden
from eden.agents._context import IterationContext
from eden.agents.simulated import simulated_agent
from eden.errors import StructuredOutputError
from eden.output import Output
from eden.sandboxes.no_sandbox import provider as no_sandbox

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
