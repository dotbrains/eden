"""REST-backed exec helpers for remote sandbox providers."""

from __future__ import annotations

import base64
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from eden.providers._impl.http_rest import RestClient
from eden.sandboxes._remote_snapshot import parse_sha256sum_snapshot, snapshot_command

RestParams = Mapping[str, object] | None


def upload_tree_via_rest_exec(
    client: RestClient,
    endpoint: str,
    *,
    src: Path,
    dst: Path,
    params: RestParams = None,
) -> None:
    for path in src.rglob("*"):
        if path.is_dir():
            continue
        rel = path.relative_to(src)
        if any(part in (".git", ".eden") for part in rel.parts):
            continue
        b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        target = dst / rel
        cmd = f"mkdir -p {target.parent.as_posix()} && echo {b64} | base64 -d > {target.as_posix()}"
        result = _post_exec(client, endpoint, command=cmd, params=params)
        if int(result.get("exit_code", result.get("exitCode", 0))) != 0:
            raise RuntimeError(f"upload of {rel} failed: {result.get('stderr', '')}")


def snapshot_via_rest_exec(
    client: RestClient,
    endpoint: str,
    *,
    root: Path,
    params: RestParams = None,
) -> dict[Path, str]:
    response = _post_exec(client, endpoint, command=snapshot_command(root), params=params)
    return parse_sha256sum_snapshot(str(response.get("stdout", "")))


def _post_exec(
    client: RestClient,
    endpoint: str,
    *,
    command: str,
    params: RestParams,
) -> dict[str, Any]:
    if params is None:
        return client.post(endpoint, json={"command": command, "wait": True})
    return client.post(endpoint, json={"command": command, "wait": True}, params=params)


__all__ = ["RestParams", "snapshot_via_rest_exec", "upload_tree_via_rest_exec"]
