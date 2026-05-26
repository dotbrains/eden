"""Parse one stream-json line emitted by cursor's ``agent --print`` mode.

Cursor's stream-json format is largely compatible with Claude Code's
(``assistant``/``result`` blocks with the same shape) with the addition
of a ``tool_call`` event for ad-hoc tool invocations. We delegate the
common cases to Claude's parser and handle ``tool_call`` here.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from eden.agents.claude_code._stream import parse_line as _parse_claude_line
from eden.streaming import StreamEvent


def parse_line(line: str, *, agent_name: str, iteration: int) -> StreamEvent | None:
    if not line.startswith("{"):
        return None
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None

    if obj.get("type") == "tool_call":
        return _parse_tool_call(obj, agent_name=agent_name, iteration=iteration)

    # Fall through to Claude-compatible parsing for assistant text /
    # tool_use blocks and the final result event (session_id + usage).
    return _parse_claude_line(line, agent_name=agent_name, iteration=iteration)


def _parse_tool_call(
    obj: dict[str, Any],
    *,
    agent_name: str,
    iteration: int,
) -> StreamEvent | None:
    name = obj.get("name") or obj.get("tool")
    tool_input = obj.get("input") or obj.get("arguments")
    if not isinstance(name, str):
        return None
    if not isinstance(tool_input, dict):
        return None
    return StreamEvent(
        type="tool_call",
        agent_name=agent_name,
        iteration=iteration,
        timestamp=datetime.now(UTC),
        tool_name=name,
        tool_input=dict(tool_input),
    )
