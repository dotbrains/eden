"""Deterministic simulated_agent — drives orchestrator code paths in tests."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from dataclasses import dataclass

from eden.agents._context import IterationContext
from eden.agents._protocol import Agent
from eden.streaming import StreamEvent


@dataclass
class _SimulatedAgent:
    name: str
    model: str
    _output: str | list[str] | Callable[[IterationContext], str]
    _delay_per_line: float
    _fail_with: Exception | None

    def build_command(self, ctx: IterationContext) -> list[str]:
        if self._fail_with is not None:
            raise self._fail_with
        if isinstance(self._output, str):
            text = self._output
        elif callable(self._output):
            text = self._output(ctx)
        else:
            text = "\n".join(self._output) + "\n"
        # Embed text and delay into a tiny Python program. JSON keeps quoting
        # safe across platforms.
        script = (
            "import sys, time, json\n"
            f"text = json.loads({json.dumps(json.dumps(text))})\n"
            f"delay = {self._delay_per_line!r}\n"
            "for line in text.split('\\n'):\n"
            "    if line == '' and not text.endswith('\\n'):\n"
            "        continue\n"
            "    sys.stdout.write(line + '\\n')\n"
            "    sys.stdout.flush()\n"
            "    if delay:\n"
            "        time.sleep(delay)\n"
        )
        return [sys.executable, "-u", "-c", script]

    def parse_stream(self, line: str) -> StreamEvent | None:
        return None


def simulated_agent(
    name: str = "simulated",
    model: str = "deterministic-1",
    *,
    output: str | list[str] | Callable[[IterationContext], str] = "<promise>COMPLETE</promise>\n",
    delay_per_line: float = 0.0,
    fail_with: Exception | None = None,
) -> Agent:
    """Build a deterministic Agent for orchestrator tests."""
    return _SimulatedAgent(
        name=name,
        model=model,
        _output=output,
        _delay_per_line=delay_per_line,
        _fail_with=fail_with,
    )
