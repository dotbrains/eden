"""Rewrite absolute path prefixes inside a JSON line."""

from __future__ import annotations

import json
from typing import Any


def rewrite_paths(line: str, *, sandbox_prefix: str, host_prefix: str) -> str:
    """Parse ``line`` as JSON, recursively walk every string value, replace any
    occurrence of ``sandbox_prefix`` at the START of the string with
    ``host_prefix``, re-encode.

    If ``line`` doesn't parse as JSON, return it unchanged.
    """
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        return line
    rewritten = _walk(obj, sandbox_prefix=sandbox_prefix, host_prefix=host_prefix)
    return json.dumps(rewritten, ensure_ascii=False)


def _walk(obj: Any, *, sandbox_prefix: str, host_prefix: str) -> Any:
    if isinstance(obj, str):
        if obj.startswith(sandbox_prefix):
            return host_prefix + obj[len(sandbox_prefix) :]
        return obj
    if isinstance(obj, list):
        return [_walk(item, sandbox_prefix=sandbox_prefix, host_prefix=host_prefix) for item in obj]
    if isinstance(obj, dict):
        return {
            k: _walk(v, sandbox_prefix=sandbox_prefix, host_prefix=host_prefix)
            for k, v in obj.items()
        }
    return obj
