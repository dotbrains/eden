"""Path and JSONL helpers for pi session storage."""

from __future__ import annotations

import json
import re
from pathlib import Path

_NON_ALNUM_RE = re.compile(r"[/\\:]")


def encode_pi_session_dir(cwd: Path) -> str:
    """Return pi's ``--<enc>--`` directory name for a given cwd."""
    s = str(cwd)
    s = s.lstrip("/\\")
    s = _NON_ALNUM_RE.sub("-", s)
    return f"--{s}--"


def _is_pi_session_filename(name: str, session_id: str) -> bool:
    """Match pi's ``<...>_<session_id>.jsonl`` convention."""
    return name.endswith(f"_{session_id}.jsonl")


def find_pi_session_path(root: Path, session_id: str) -> Path | None:
    """Walk ``root`` for a pi session JSONL matching ``session_id``."""
    if not root.exists():
        return None
    try:
        entries = list(root.iterdir())
    except OSError:
        return None
    for entry in entries:
        try:
            if not entry.is_dir():
                continue
            for f in entry.iterdir():
                if f.is_file() and _is_pi_session_filename(f.name, session_id):
                    return f
        except OSError:
            continue
    return None


def transfer_pi_session(jsonl: str, from_cwd: Path, to_cwd: Path) -> str:
    """Rewrite the session header's ``cwd`` field from ``from_cwd`` to ``to_cwd``."""
    if jsonl == "":
        return ""
    from_s = from_cwd.as_posix()
    to_s = to_cwd.as_posix()
    out: list[str] = []
    for line in jsonl.split("\n"):
        if line == "":
            out.append(line)
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            out.append(line)
            continue
        if (
            isinstance(entry, dict)
            and entry.get("type") == "session"
            and entry.get("cwd") == from_s
        ):
            entry["cwd"] = to_s
            out.append(json.dumps(entry, ensure_ascii=False))
        else:
            out.append(line)
    return "\n".join(out)


def read_session_cwd(jsonl: str) -> str | None:
    """Return the ``cwd`` value from the session header, or ``None``."""
    for line in jsonl.split("\n"):
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(entry, dict) and entry.get("type") == "session":
            cwd = entry.get("cwd")
            return cwd if isinstance(cwd, str) else None
    return None


__all__ = [
    "encode_pi_session_dir",
    "find_pi_session_path",
    "read_session_cwd",
    "transfer_pi_session",
]
