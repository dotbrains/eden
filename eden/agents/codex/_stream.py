"""Parse one stream-json line emitted by `codex`.

Maps codex's JSONL events to Eden StreamEvents:

- ``{"type":"thread.started","thread_id":"..."}`` → ``StreamEvent(type="session_id")``.
- ``{"type":"item.completed","item":{"type":"agent_message","text":"..."}}``
  → ``StreamEvent(type="text", text=...)``.
- ``{"type":"item.started","item":{"type":"command_execution","command":"..."}}``
  → ``StreamEvent(type="tool_call", tool_name="Bash", tool_input={"command": ...})``.
- ``{"type":"turn.completed","usage":{"input_tokens":N,"cached_input_tokens":N,
  "output_tokens":N}}`` → ``StreamEvent(type="usage", usage=Usage(...))``
  so ``Iteration.usage`` populates for codex (matches claude_code).
- ``{"type":"error", ...}`` → ``StreamEvent(type="text", text=<error message>)``
  so the failure surfaces in live display / file logs (also parsed
  out-of-band by ``parse_stdout_error`` for ``AgentError.parsed_error``).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from eden._types import Usage
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

    if kind == "turn.completed":
        usage = _parse_codex_usage(obj.get("usage"))
        if usage is not None:
            return StreamEvent(
                type="usage",
                agent_name=agent_name,
                iteration=iteration,
                timestamp=now,
                usage=usage,
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


def _parse_codex_usage(raw: Any) -> Usage | None:
    """Map codex's ``usage`` payload to Eden's ``Usage`` dataclass.

    Codex reports the total ``input_tokens`` (including cache hits) and a
    separate ``cached_input_tokens`` count. Eden's ``Usage.input_tokens``
    counts only non-cached input, with cache hits in
    ``cache_read_input_tokens`` (matching Claude's accounting), so subtract
    cached from total.
    """
    if not isinstance(raw, dict):
        return None
    input_tokens = raw.get("input_tokens")
    cached = raw.get("cached_input_tokens")
    output_tokens = raw.get("output_tokens")
    if not (
        isinstance(input_tokens, int) and isinstance(cached, int) and isinstance(output_tokens, int)
    ):
        return None
    return Usage(
        input_tokens=input_tokens - cached,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=cached,
        output_tokens=output_tokens,
    )


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
