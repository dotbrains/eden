"""Tag-based structured-output extraction with fence-aware JSON unwrap."""

from __future__ import annotations

import json
import re
from pathlib import Path

from eden.errors import StructuredOutputError
from eden.output._types import OutputDefinition, _OutputObject, _OutputString

_FENCE_RE = re.compile(r"^```(?:json)?\s*\n([\s\S]*?)\n\s*```\s*$")


def _find_last_tag(text: str, tag: str) -> str | None:
    """Return contents of the **last** ``<tag>...</tag>`` pair, or ``None``."""
    open_t = f"<{tag}>"
    close_t = f"</{tag}>"
    last: str | None = None
    pos = 0
    while True:
        oi = text.find(open_t, pos)
        if oi < 0:
            break
        cs = oi + len(open_t)
        ci = text.find(close_t, cs)
        if ci < 0:
            break
        last = text[cs:ci]
        pos = ci + len(close_t)
    return last


def _unwrap_fences(text: str) -> str:
    m = _FENCE_RE.match(text)
    if m:
        return m.group(1).strip()
    return text


def extract_structured_output(
    stdout: str,
    definition: OutputDefinition,
    *,
    branch: str,
    preserved_worktree_path: Path | None = None,
    session_id: str | None = None,
    session_file_path: Path | None = None,
) -> object:
    """Extract + validate the configured tag's payload from ``stdout``.

    Raises ``StructuredOutputError`` on missing tag, invalid JSON, or failed
    schema validation. Returns the validated value (string for
    ``Output.string``, schema-returned ``T`` for ``Output.object``).

    ``session_id`` / ``session_file_path``, when provided by the
    orchestrator, are stamped onto the raised error so callers can
    resume the failed session with corrective feedback rather than
    restart from scratch.
    """
    if isinstance(definition, _OutputString):
        raw = _find_last_tag(stdout, definition.tag)
        if raw is None:
            raise StructuredOutputError(
                code="output.tag_missing",
                message=(f"structured output tag <{definition.tag}> not found in agent output"),
                tag=definition.tag,
                raw_matched=None,
                branch=branch,
                preserved_worktree_path=preserved_worktree_path,
                session_id=session_id,
                session_file_path=session_file_path,
            )
        return raw.strip()

    # _OutputObject
    assert isinstance(definition, _OutputObject)
    raw = _find_last_tag(stdout, definition.tag)
    if raw is None:
        raise StructuredOutputError(
            code="output.tag_missing",
            message=(f"structured output tag <{definition.tag}> not found in agent output"),
            tag=definition.tag,
            raw_matched=None,
            branch=branch,
            preserved_worktree_path=preserved_worktree_path,
            session_id=session_id,
            session_file_path=session_file_path,
        )
    unwrapped = _unwrap_fences(raw.strip())
    try:
        parsed = json.loads(unwrapped)
    except json.JSONDecodeError as exc:
        raise StructuredOutputError(
            code="output.invalid_json",
            message=(f"structured output tag <{definition.tag}> contains invalid JSON"),
            tag=definition.tag,
            raw_matched=raw,
            branch=branch,
            preserved_worktree_path=preserved_worktree_path,
            session_id=session_id,
            session_file_path=session_file_path,
            cause=exc,
        ) from exc
    try:
        return definition.schema(parsed)
    except Exception as exc:
        raise StructuredOutputError(
            code="output.validation_failed",
            message=(f"structured output tag <{definition.tag}> failed schema validation"),
            tag=definition.tag,
            raw_matched=raw,
            branch=branch,
            preserved_worktree_path=preserved_worktree_path,
            session_id=session_id,
            session_file_path=session_file_path,
            cause=exc,
        ) from exc
