"""docker provider: bind-mount sandbox running commands inside a docker container."""

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
) -> SandboxProvider:
    """Build a docker bind-mount SandboxProvider.

    ``container_uid`` / ``container_gid`` set the in-container user. When left
    as ``None`` (default), eden uses the host's UID/GID so files written into
    the bind-mounted worktree land with the host user as owner — matching the
    permissions the agent's outputs would have if it ran natively. A pre-flight
    ``docker image inspect`` raises ``ImageUidMismatch`` when the image was
    built for a different UID; rebuild with
    ``--build-arg AGENT_UID=<host-uid> AGENT_GID=<host-gid>`` to align them.

    ``selinux_label`` controls the bind-mount relabel suffix (``"z"`` shared,
    ``"Z"`` private, ``None`` disabled). Default ``"z"`` is required for SELinux
    hosts (Fedora, RHEL) and harmless on non-SELinux hosts.
    """
    return make_container_provider(
        binary="docker",
        image=image,
        mounts=mounts,
        env=env,
        network=network,
        container_uid=container_uid,
        container_gid=container_gid,
        selinux_label=selinux_label,
    )


__all__ = ["provider"]
