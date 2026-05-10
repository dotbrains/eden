"""Shared helpers for extracting agent-emitted error text from stdout.

Codex, Pi, and OpenCode surface error details on **stdout** rather than
stderr — Codex/Pi as JSON ``{"type": "error", ...}`` events; OpenCode as a
final ``result`` text field with ``is_error: true``. Without parsing these,
``AgentError`` raised on a non-zero exit would carry an empty message
because ``stderr`` is empty.
"""

from __future__ import annotations

import json


def parse_stdout_error(stdout: str) -> str | None:
    """Return the most informative error text found in ``stdout`` or ``None``.

    Scans line-by-line. Recognises three shapes (last match wins so callers
    see the agent's most recent complaint):

    - ``{"type": "error", "message": "..."}`` — Codex/Pi JSON event.
    - ``{"type": "result", "is_error": true, "result": "..."}`` — OpenCode
      result text wrapper.
    - Lines starting with ``Error:`` or ``error:`` — best-effort fallback for
      plain-text emitters.

    Non-JSON lines and unrecognised event shapes are skipped silently.
    """
    last: str | None = None
    for raw in stdout.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("{"):
            try:
                obj = json.loads(line)
            except (ValueError, json.JSONDecodeError):
                pass
            else:
                msg = _extract_json_error(obj)
                if msg:
                    last = msg
                    continue
        lowered = line.lower()
        if lowered.startswith("error:") or lowered.startswith("fatal:"):
            last = line
    return last


def _extract_json_error(obj: object) -> str | None:
    """Return error text from a single decoded JSON event, or ``None``."""
    if not isinstance(obj, dict):
        return None
    typ = obj.get("type")
    if typ == "error":
        msg = obj.get("message") or obj.get("error") or obj.get("detail")
        if isinstance(msg, str) and msg:
            return msg
        # Fall through: stringify the whole object so the user sees something.
        return str(obj)
    if typ == "result" and obj.get("is_error") is True:
        msg = obj.get("result") or obj.get("error") or obj.get("message")
        if isinstance(msg, str) and msg:
            return msg
    return None


__all__ = ["parse_stdout_error"]
