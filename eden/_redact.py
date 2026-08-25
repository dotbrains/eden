"""Secret redaction for error messages and REST debug fields."""

from __future__ import annotations

import re

_REDACTED = "<redacted>"

# Value-preserving patterns: keep the prefix/key, redact the secret value.
_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)(token=)([^\s&'\"]+)"),
    re.compile(r"(?i)(key=)([^\s&'\"]+)"),
    re.compile(r"(?i)(secret=)([^\s&'\"]+)"),
    re.compile(r"(?i)(password=)([^\s&'\"]+)"),
    re.compile(r"(?i)(Authorization:\s*Bearer\s+)([^\s]+)"),
    re.compile(r"(?i)(\bBearer\s+)([^\s]+)"),
)


def redact_secrets(text: str) -> str:
    """Replace common secret-bearing patterns with ``<redacted>``."""
    out = text
    for pattern in _PATTERNS:
        out = pattern.sub(rf"\1{_REDACTED}", out)
    return out


__all__ = ["redact_secrets"]
