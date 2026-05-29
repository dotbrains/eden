"""Parse one stream-json line emitted by `pi`.

Maps pi's JSONL events to Eden StreamEvents:

- ``{"type":"message_update","assistantMessageEvent":{"type":"text_delta","delta":"..."}}``
  → ``StreamEvent(type="text", text=<delta>)``. Each delta is typically a
  small token chunk; downstream consumers can accumulate via
  :class:`eden.streaming.TextDeltaBuffer`.
- ``{"type":"tool_execution_start","toolName":"Bash","args":{"command":"..."}}``
  → ``StreamEvent(type="tool_call", tool_name="Bash", tool_input=<args>)``
  for known tools (see :data:`TOOL_ARG_FIELDS`).
- ``{"type":"agent_end","messages":[...]}`` → ``StreamEvent(type="text",
  text=<last assistant message concatenated>)``.
- ``{"type":"agent_error"|"error", ...}`` → ``StreamEvent(type="text",
  text=<error message>)``.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from eden.streaming import StreamEvent

# Tools whose execution start events should surface as tool_call StreamEvents.
# The value is the field within ``args`` whose presence (and string type)
# determines emission. Mirrors upstream's TOOL_ARG_FIELDS map.
TOOL_ARG_FIELDS: dict[str, str] = {
    "Bash": "command",
    "WebSearch": "query",
    "WebFetch": "url",
    "Agent": "description",
}


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

    if kind == "session":
        # First line of pi's --mode json stdout stream is a session header
        # carrying the UUID. Subsequent entries (model_change, message_update,
        # ...) do not. Surfacing the id as a ``session_id`` event lets the
        # orchestrator route capture / resume via ``PiSessionStorage``.
        sid = obj.get("id")
        if isinstance(sid, str):
            return StreamEvent(
                type="session_id",
                agent_name=agent_name,
                iteration=iteration,
                timestamp=now,
                session_id=sid,
            )
        return None

    if kind == "message_update":
        evt = obj.get("assistantMessageEvent")
        if (
            isinstance(evt, dict)
            and evt.get("type") == "text_delta"
            and isinstance(evt.get("delta"), str)
        ):
            return StreamEvent(
                type="text",
                agent_name=agent_name,
                iteration=iteration,
                timestamp=now,
                text=evt["delta"],
            )
        return None

    if kind == "tool_execution_start":
        tool_name = obj.get("toolName")
        args = obj.get("args")
        if not (isinstance(tool_name, str) and isinstance(args, dict)):
            return None
        arg_field = TOOL_ARG_FIELDS.get(tool_name)
        if arg_field is None:
            return None
        if not isinstance(args.get(arg_field), str):
            return None
        return StreamEvent(
            type="tool_call",
            agent_name=agent_name,
            iteration=iteration,
            timestamp=now,
            tool_name=tool_name,
            tool_input=dict(args),
        )

    if kind in ("agent_error", "error"):
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

    if kind == "agent_end":
        messages = obj.get("messages")
        if not isinstance(messages, list):
            return None
        for msg in reversed(messages):
            if not isinstance(msg, dict):
                continue
            if msg.get("role") != "assistant":
                # First non-assistant message from the end breaks the
                # search — matches upstream's behavior.
                break
            content = msg.get("content")
            if not isinstance(content, list):
                continue
            texts: list[str] = []
            for block in content:
                if (
                    isinstance(block, dict)
                    and block.get("type") == "text"
                    and isinstance(block.get("text"), str)
                ):
                    texts.append(block["text"])
            if texts:
                return StreamEvent(
                    type="text",
                    agent_name=agent_name,
                    iteration=iteration,
                    timestamp=now,
                    text="".join(texts),
                )
            break
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
