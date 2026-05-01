"""docker provider: bind-mount sandbox running commands inside a docker container."""

from __future__ import annotations

from collections.abc import Mapping

from eden.providers._impl.container import make_container_provider
from eden.providers._protocols import SandboxProvider
from eden.providers._types import Mount


def provider(
    *,
    image: str,
    mounts: tuple[Mount, ...] | None = None,
    env: Mapping[str, str] | None = None,
    network: str | None = None,
) -> SandboxProvider:
    return make_container_provider(
        binary="docker",
        image=image,
        mounts=mounts,
        env=env,
        network=network,
    )


__all__ = ["provider"]
