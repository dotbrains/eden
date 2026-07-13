"""Post-start preparation for container sandboxes."""

from __future__ import annotations

import subprocess
from collections.abc import Mapping
from pathlib import Path

from eden.providers._impl.container_mounts import (
    SANDBOX_HOMEDIR,
    _ensure_mount_parents,
    _file_mount_parents,
)
from eden.providers._types import Mount
from eden.sandboxes.errors import ContainerStartFailed


def prepare_file_mount_parents(
    *,
    binary: str,
    container_id: str,
    mount_map: Mapping[Path, Mount],
    uid: int,
    gid: int,
) -> None:
    parents = _file_mount_parents(list(mount_map.values()), sandbox_homedir=SANDBOX_HOMEDIR)
    if not parents:
        return
    try:
        _ensure_mount_parents(
            binary=binary,
            container_id=container_id,
            parents=parents,
            uid=uid,
            gid=gid,
        )
    except ContainerStartFailed:
        subprocess.run([binary, "kill", container_id], capture_output=True, text=True)
        raise


__all__ = ["prepare_file_mount_parents"]
