"""Shared helper for ``copy_file_in`` directory uploads on exec-only providers.

REST-based providers (Vercel, Daytona) can only move data through ``exec``.
Mirroring sandcastle's ``copyIn`` semantics, when the host path is a
directory we tar+gzip it locally, base64-encode, ship as a single ``exec``
call, then untar inside the sandbox.
"""

from __future__ import annotations

import base64
import io
import tarfile
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Protocol

from eden.providers._types import ExecResult


class _Exec(Protocol):
    def __call__(
        self,
        cmd: str,
        *,
        on_line: Callable[[str], None] | None = None,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> ExecResult: ...


def upload_dir_via_tar(exec_fn: _Exec, *, host: Path, sandbox: Path) -> ExecResult:
    """Tar+gzip ``host``, base64-encode, untar at ``sandbox`` inside the box.

    Returns the final ``exec`` ``ExecResult`` so the caller can decide how
    to surface failures. Equivalent to sandcastle's ``copyIn`` directory
    branch — single round-trip, no streaming.
    """
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        # ``arcname=""`` so entries live at the archive root; the sandbox
        # then extracts straight into ``sandbox`` without a wrapper dir.
        tar.add(str(host), arcname=".")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    target = sandbox.as_posix()
    cmd = f"mkdir -p {target} && echo {b64} | base64 -d | tar -xzf - -C {target}"
    return exec_fn(cmd)
