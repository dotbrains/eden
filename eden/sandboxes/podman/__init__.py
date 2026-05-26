"""podman provider: bind-mount sandbox running commands inside a podman container."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from eden.providers._impl.container import make_container_provider
from eden.providers._protocols import SandboxProvider
from eden.providers._types import Mount


def provider(
    *,
    image: str,
    mounts: tuple[Mount, ...] | None = None,
    env: Mapping[str, str] | None = None,
    network: str | None = None,
    container_uid: int | None = None,
    container_gid: int | None = None,
    selinux_label: Literal["z", "Z"] | None = "z",
    devices: tuple[str, ...] | None = None,
    cpus: float | None = None,
    groups: tuple[str | int, ...] | None = None,
) -> SandboxProvider:
    """Build a podman bind-mount SandboxProvider.

    See :func:`eden.sandboxes.docker.provider` for the meaning of
    ``container_uid`` / ``container_gid``, ``selinux_label``, ``devices``,
    ``cpus``, and ``groups``; podman behaves identically.
    """
    return make_container_provider(
        binary="podman",
        image=image,
        mounts=mounts,
        env=env,
        network=network,
        container_uid=container_uid,
        container_gid=container_gid,
        selinux_label=selinux_label,
        devices=devices,
        cpus=cpus,
        groups=groups,
    )


__all__ = ["provider"]
