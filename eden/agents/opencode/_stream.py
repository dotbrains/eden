"""Parse one stream-json line emitted by ``opencode run --format json``.

Maps opencode's JSONL events to Eden StreamEvents:

- ``{"type":"step_start","sessionID":"..."}`` →
  ``StreamEvent(type="session_id", session_id=...)``.
- ``{"type":"text","part":{"type":"text","text":"..."}}`` →
  ``StreamEvent(type="text", text=...)``.
- ``{"type":"tool_use","part":{"type":"tool","tool":"<name>","state":{
  "status":"completed","input":{...}}}}`` →
  ``StreamEvent(type="tool_call", tool_name=<name>, tool_input=<input>)``.
- ``{"type":"error", ...}`` → ``StreamEvent(type="text", text=<error message>)``
  so the failure surfaces in live display / file logs.
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
    part = obj.get("part")

    if kind == "step_start":
        session_id = obj.get("sessionID")
        if isinstance(session_id, str) and session_id:
            return StreamEvent(
                type="session_id",
                agent_name=agent_name,
                iteration=iteration,
                timestamp=now,
                session_id=session_id,
            )
        return None

    if kind == "text" and isinstance(part, dict):
        if part.get("type") == "text" and isinstance(part.get("text"), str):
            return StreamEvent(
                type="text",
                agent_name=agent_name,
                iteration=iteration,
                timestamp=now,
                text=part["text"],
            )
        return None

    if kind == "tool_use" and isinstance(part, dict):
        if part.get("type") != "tool":
            return None
        tool_name = part.get("tool")
        state = part.get("state")
        if not (isinstance(tool_name, str) and isinstance(state, dict)):
            return None
        # Mirror upstream: only emit completed tool calls. In-flight states
        # (pending / running) would create noise without finalized input.
        if state.get("status") != "completed":
            return None
        tool_input = state.get("input")
        if not isinstance(tool_input, dict):
            return None
        return StreamEvent(
            type="tool_call",
            agent_name=agent_name,
            iteration=iteration,
            timestamp=now,
            tool_name=tool_name,
            tool_input=dict(tool_input),
        )

    if kind == "error":
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
