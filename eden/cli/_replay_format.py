"""Formatting helpers for `eden replay`."""

from __future__ import annotations

from typing import Any


def format_user(obj: dict[str, Any]) -> str | None:
    msg = obj.get("message")
    if not isinstance(msg, dict):
        return None
    content = msg.get("content")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return None
    parts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text":
            text = block.get("text")
            if isinstance(text, str):
                parts.append(text)
        elif block.get("type") == "tool_result":
            raw = block.get("content")
            if isinstance(raw, str):
                parts.append(f"[tool result] {raw}")
    return "\n".join(parts) if parts else None


def format_assistant(obj: dict[str, Any]) -> tuple[list[str], list[tuple[str, dict[str, Any]]]]:
    """Return (text-blocks, [(tool_name, tool_input), ...]) from an assistant entry."""
    msg = obj.get("message")
    text_blocks: list[str] = []
    tool_uses: list[tuple[str, dict[str, Any]]] = []
    if not isinstance(msg, dict):
        return text_blocks, tool_uses
    content = msg.get("content")
    if not isinstance(content, list):
        return text_blocks, tool_uses
    for block in content:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype == "text":
            text = block.get("text")
            if isinstance(text, str):
                text_blocks.append(text)
        elif btype == "tool_use":
            name = block.get("name")
            tool_input = block.get("input") or {}
            if isinstance(name, str) and isinstance(tool_input, dict):
                tool_uses.append((name, tool_input))
    return text_blocks, tool_uses


def short_input(tool_input: dict[str, Any]) -> str:
    """Return a one-line summary of a tool_use's input args."""
    parts = []
    for k, v in tool_input.items():
        v_str = str(v)
        if len(v_str) > 80:
            v_str = v_str[:77] + "..."
        parts.append(f"{k}={v_str}")
    return ", ".join(parts)


__all__ = ["format_assistant", "format_user", "short_input"]
