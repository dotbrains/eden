"""Host identity helpers for container providers."""

from __future__ import annotations

import os


def host_uid() -> int:
    """Return the host's UID, or 1000 on platforms without ``getuid``."""
    getuid = getattr(os, "getuid", None)
    return getuid() if getuid is not None else 1000


def host_gid() -> int:
    """Return the host's GID, or 1000 on platforms without ``getgid``."""
    getgid = getattr(os, "getgid", None)
    return getgid() if getgid is not None else 1000
