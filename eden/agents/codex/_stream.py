"""Parse one stream-json line emitted by `codex`.

Maps codex's JSONL events to Eden StreamEvents:

- ``{"type":"thread.started","thread_id":"..."}`` → ``StreamEvent(type="session_id")``.
- ``{"type":"item.completed","item":{"type":"agent_message","text":"..."}}``
  → ``StreamEvent(type="text", text=...)``.
- ``{"type":"item.started","item":{"type":"command_execution","command":"..."}}``
  → ``StreamEvent(type="tool_call", tool_name="Bash", tool_input={"command": ...})``.
- ``{"type":"error", ...}`` → ``StreamEvent(type="text", text=<error message>)``
  so the failure surfaces in live display / file logs (also parsed
  out-of-band by ``parse_stdout_error`` for ``AgentError.parsed_error``).
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

    if kind == "thread.started":
        thread_id = obj.get("thread_id")
        if isinstance(thread_id, str) and thread_id:
            return StreamEvent(
                type="session_id",
                agent_name=agent_name,
                iteration=iteration,
                timestamp=now,
                session_id=thread_id,
            )
        return None

    if kind == "item.completed":
        item = obj.get("item")
        if (
            isinstance(item, dict)
            and item.get("type") == "agent_message"
            and isinstance(item.get("text"), str)
        ):
            return StreamEvent(
                type="text",
                agent_name=agent_name,
                iteration=iteration,
                timestamp=now,
                text=item["text"],
            )
        return None

    if kind == "item.started":
        item = obj.get("item")
        if (
            isinstance(item, dict)
            and item.get("type") == "command_execution"
            and isinstance(item.get("command"), str)
        ):
            return StreamEvent(
                type="tool_call",
                agent_name=agent_name,
                iteration=iteration,
                timestamp=now,
                tool_name="Bash",
                tool_input={"command": item["command"]},
            )
        return None

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
