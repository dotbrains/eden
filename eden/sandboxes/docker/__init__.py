"""docker provider: bind-mount sandbox running commands inside a docker container."""

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
    ports: tuple[int, ...] | None = None,
    max_output_tail_chars: int = DEFAULT_MAX_CHARS,
    create_timeout: float = 120.0,
) -> SandboxProvider:
    """Build a docker bind-mount SandboxProvider.

    ``image`` defaults to ``eden:<repo-dir>`` using the host repository path
    passed when the sandbox is created.

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

    ``devices`` exposes host devices into the container (``--device <spec>``).
    Useful for GPU workloads (``("/dev/dri:/dev/dri:rwm",)``) or KVM
    nesting (``("/dev/kvm",)``).

    ``cpus`` bounds the container's CPU usage (``--cpus <value>``). Useful
    when several sandboxes share a host.

    ``groups`` adds supplementary groups to the in-container user
    (``--group-add``); most commonly ``("docker",)`` for Docker-in-Docker
    setups that bind-mount the host socket.

    ``max_output_tail_chars`` bounds the stdout/stderr retained in
    ``ExecResult`` for streamed exec calls; live ``on_line`` callbacks still
    receive every line.

    ``create_timeout`` bounds the whole container-creation sequence (image
    inspect, UID check, ``docker run``, mount-parent prep) against one shared
    deadline, not each step independently — a hung daemon otherwise costs up
    to N times the intended deadline across N sequential subprocess calls.
    Raises ``ContainerStartTimeout`` on expiry.
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
        devices=devices,
        cpus=cpus,
        groups=groups,
        max_output_tail_chars=max_output_tail_chars,
        create_timeout=create_timeout,
        ports=ports,
    )


__all__ = ["provider"]
