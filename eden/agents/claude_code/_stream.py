"""Parse one stream-json line emitted by `claude --output-format stream-json --verbose`."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from eden._types import Usage
from eden.streaming import StreamEvent


def parse_line(line: str, *, agent_name: str, iteration: int) -> StreamEvent | None:
    """Decode one stream-json line and return a StreamEvent.

    Returns:
        - StreamEvent(type="text", ...) for assistant text blocks (first one wins).
        - StreamEvent(type="tool_call", ...) for assistant tool_use blocks.
        - StreamEvent(type="usage", ...) for the final result line (must carry usage).
        - None for system / user / thinking / unknown / malformed lines.
    """
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None
    kind = obj.get("type")
    now = datetime.now(UTC)
    if kind == "assistant":
        return _parse_assistant(obj, agent_name=agent_name, iteration=iteration, now=now)
    if kind == "result":
        return _parse_result(obj, agent_name=agent_name, iteration=iteration, now=now)
    return None


def _parse_assistant(
    obj: dict[str, Any],
    *,
    agent_name: str,
    iteration: int,
    now: datetime,
) -> StreamEvent | None:
    message = obj.get("message")
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    if not isinstance(content, list):
        return None
    for block in content:
        if not isinstance(block, dict):
            continue
        block_type = block.get("type")
        if block_type == "text":
            text = block.get("text")
            if isinstance(text, str):
                return StreamEvent(
                    type="text",
                    agent_name=agent_name,
                    iteration=iteration,
                    timestamp=now,
                    text=text,
                )
        elif block_type == "tool_use":
            name = block.get("name")
            tool_input = block.get("input")
            if isinstance(name, str) and isinstance(tool_input, dict):
                return StreamEvent(
                    type="tool_call",
                    agent_name=agent_name,
                    iteration=iteration,
                    timestamp=now,
                    tool_name=name,
                    tool_input=tool_input,
                )
    return None


def _parse_result(
    obj: dict[str, Any],
    *,
    agent_name: str,
    iteration: int,
    now: datetime,
) -> StreamEvent | None:
    session_id = obj.get("session_id")
    raw_usage = obj.get("usage")
    if not isinstance(session_id, str) or not isinstance(raw_usage, dict):
        return None
    try:
        usage = Usage(
            input_tokens=int(raw_usage.get("input_tokens", 0)),
            cache_creation_input_tokens=int(raw_usage.get("cache_creation_input_tokens", 0)),
            cache_read_input_tokens=int(raw_usage.get("cache_read_input_tokens", 0)),
            output_tokens=int(raw_usage.get("output_tokens", 0)),
        )
    except (TypeError, ValueError):
        return None
    return StreamEvent(
        type="usage",
        agent_name=agent_name,
        iteration=iteration,
        timestamp=now,
        usage=usage,
        session_id=session_id,
    )
