"""Remote exec payload helpers for Daytona sandboxes."""

from __future__ import annotations

import base64
from collections.abc import Mapping
from pathlib import Path


def build_exec_payload(
    cmd: str,
    *,
    cwd: Path | None,
    env: Mapping[str, str] | None,
    timeout: float | None,
    stdin: str | None,
) -> dict[str, object]:
    if stdin is not None:
        b64 = base64.b64encode(stdin.encode("utf-8")).decode("ascii")
        cmd = f"printf '%s' {b64} | base64 -d | ({cmd})"
    payload: dict[str, object] = {"command": cmd}
    if cwd is not None:
        payload["cwd"] = cwd.as_posix()
    if env:
        payload["env"] = dict(env)
    if timeout is not None:
        payload["timeout"] = timeout
    return payload
