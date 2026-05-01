"""Secret redactor for log lines."""

from __future__ import annotations

import re
from collections.abc import Iterable

_REDACTED = "<redacted>"

_PREFIX_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-ant-[A-Za-z0-9_\-]+"),
    re.compile(r"ghp_[A-Za-z0-9]+"),
    re.compile(r"xoxb-[A-Za-z0-9\-]+"),
    re.compile(r"xoxp-[A-Za-z0-9\-]+"),
)


def redact(text: str, *, env_values: Iterable[str]) -> str:
    """Replace known secret prefixes and supplied env-var values with <redacted>.

    Env values shorter than 3 chars are skipped to avoid mangling normal text.
    """
    out = text
    for pattern in _PREFIX_PATTERNS:
        out = pattern.sub(_REDACTED, out)
    for value in env_values:
        if len(value) < 3:
            continue
        out = out.replace(value, _REDACTED)
    return out
