"""Secret redactor for log lines."""

from __future__ import annotations

import re
from collections.abc import Iterable

_REDACTED = "<redacted>"

# Secret-prefix patterns. Anchored on well-known formats so false positives
# stay rare. Generic high-entropy strings are deliberately NOT matched —
# false-positive redaction in user-visible logs is its own form of bug.
_PREFIX_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Anthropic
    re.compile(r"sk-ant-[A-Za-z0-9_\-]+"),
    # OpenAI: legacy `sk-...` and project-scoped `sk-proj-...` (40+ chars).
    # Pattern requires a word boundary then ≥20 chars to avoid matching
    # placeholder strings like "sk-foo".
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_\-]{20,}"),
    # GitHub: classic PAT, fine-grained PAT, and OAuth/Server tokens.
    re.compile(r"ghp_[A-Za-z0-9]+"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"gho_[A-Za-z0-9]+"),
    re.compile(r"ghs_[A-Za-z0-9]+"),
    # Slack
    re.compile(r"xoxb-[A-Za-z0-9\-]+"),
    re.compile(r"xoxp-[A-Za-z0-9\-]+"),
    # AWS access keys (AKIA + 16 uppercase alphanumerics).
    re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
    # Stripe live keys (test keys are public; only `_live_` is a secret).
    re.compile(r"\b[sr]k_live_[A-Za-z0-9]{20,}"),
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
