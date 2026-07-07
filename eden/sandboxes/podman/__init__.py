"""podman provider: bind-mount sandbox running commands inside a podman container."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from eden.providers._impl.container import make_container_provider
from eden.providers._protocols import SandboxProvider
from eden.providers._types import Mount
from eden.streaming._bounded_tail import DEFAULT_MAX_CHARS


def provider(
    *,
    image: str | None = None,
    mounts: tuple[Mount, ...] | None = None,
    env: Mapping[str, str] | None = None,
    network: str | tuple[str, ...] | None = None,
    container_uid: int | None = None,
    container_gid: int | None = None,
    selinux_label: Literal["z", "Z"] | None = "z",
    devices: tuple[str, ...] | None = None,
    cpus: float | None = None,
    groups: tuple[str | int, ...] | None = None,
    userns: Literal["keep-id"] | None = "keep-id",
    max_output_tail_chars: int = DEFAULT_MAX_CHARS,
) -> SandboxProvider:
    """Build a podman bind-mount SandboxProvider.

    ``image`` defaults to ``eden:<repo-dir>`` using the host repository path
    passed when the sandbox is created.

    See :func:`eden.sandboxes.docker.provider` for the meaning of
    ``container_uid`` / ``container_gid``, ``selinux_label``, ``devices``,
    ``cpus``, and ``groups``.

    ``userns="keep-id"`` (default) adds Podman's rootless
    ``--userns=keep-id:uid=<uid>,gid=<gid>`` mapping so the host user appears
    as the configured in-container agent user. Pass ``userns=None`` for rootful
    Podman or custom namespace setups.

    ``max_output_tail_chars`` bounds the stdout/stderr retained in
    ``ExecResult`` for streamed exec calls; live ``on_line`` callbacks still
    receive every line.
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
        userns=userns,
        max_output_tail_chars=max_output_tail_chars,
    )


__all__ = ["provider"]
