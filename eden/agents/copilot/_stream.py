"""Parse one stream-json line emitted by ``copilot -p ... --output-format json``.

Maps Copilot's JSONL events to Eden StreamEvents:

- ``{"type":"assistant.message_delta","data":{"deltaContent":"..."}}`` →
  ``StreamEvent(type="text", text=<delta>)``.
- ``{"type":"tool.execution_start","data":{"toolName":"<name>",
  "arguments":{...}}}`` → ``StreamEvent(type="tool_call", tool_name=...,
  tool_input=<arguments>)``. ``"bash"`` is normalised to ``"Bash"`` for
  parity with the other agents.
- ``{"type":"result","sessionId":"..."}`` →
  ``StreamEvent(type="session_id", session_id=...)``.
- ``{"type":"error"|"agent_error", ...}`` →
  ``StreamEvent(type="text", text=<error message>)``.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

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
    now = datetime.now(UTC)
    kind = obj.get("type")
    data = obj.get("data")

    if kind == "assistant.message_delta" and isinstance(data, dict):
        delta = data.get("deltaContent")
        if isinstance(delta, str) and delta:
            return StreamEvent(
                type="text",
                agent_name=agent_name,
                iteration=iteration,
                timestamp=now,
                text=delta,
            )
        return None

    if kind == "tool.execution_start" and isinstance(data, dict):
        raw_name = data.get("toolName")
        args = data.get("arguments")
        if not (isinstance(raw_name, str) and isinstance(args, dict)):
            return None
        # Upstream normalises lowercase "bash" → "Bash" so the event matches
        # the other agents' Bash tool_call shape.
        tool_name = "Bash" if raw_name == "bash" else raw_name
        return StreamEvent(
            type="tool_call",
            agent_name=agent_name,
            iteration=iteration,
            timestamp=now,
            tool_name=tool_name,
            tool_input=dict(args),
        )

    if kind == "result":
        session_id = obj.get("sessionId")
        if isinstance(session_id, str) and session_id:
            return StreamEvent(
                type="session_id",
                agent_name=agent_name,
                iteration=iteration,
                timestamp=now,
                session_id=session_id,
            )
        return None

    if kind in ("error", "agent_error"):
        msg = _extract_error_message(obj)
        if msg:
            return StreamEvent(
                type="text",
                agent_name=agent_name,
                iteration=iteration,
                timestamp=now,
                text=msg,
            )
        return None

    return None


def _extract_error_message(obj: dict[str, Any]) -> str | None:
    err = obj.get("error")
    if isinstance(err, str):
        return err
    if isinstance(err, dict):
        msg = err.get("message")
        if isinstance(msg, str):
            return msg
    msg = obj.get("message")
    if isinstance(msg, str):
        return msg
    return None
