"""Shared branch-name sanitizer for session capture paths.

Hoisted out of ``eden.session.__init__`` so per-agent SessionStorage
implementations (claude, codex, …) can import it without circular
imports through the package init.
"""

from __future__ import annotations

import re

# Mirrors eden.logging._file._BRANCH_SANITIZE for consistency.
_BRANCH_SANITIZE = re.compile(r"[^A-Za-z0-9._-]+")
_BRANCH_MAX = 64


def sanitize_branch(branch: str) -> str:
    safe = _BRANCH_SANITIZE.sub("-", branch).strip("-")
    if not safe:
        safe = "run"
    if len(safe) > _BRANCH_MAX:
        safe = safe[:_BRANCH_MAX]
    return safe


__all__ = ["sanitize_branch"]
