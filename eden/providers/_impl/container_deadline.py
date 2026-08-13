"""Shared wall-clock deadline for the docker/podman container-start sequence.

Sandcastle wraps its whole ``provider.create()`` call in one timeout
(``ContainerStartTimeoutError``, ``startSandbox.ts``) rather than giving each
host-side step (image inspect, UID check, ``docker run``/``podman run``,
mount-parent prep) its own independent budget — a hung daemon could
otherwise cost up to N times the intended deadline across N sequential
subprocess calls, since ``subprocess.run(timeout=...)`` only bounds a single
call. ``container_start_deadline`` gives each step ``remaining()`` seconds
against one shared deadline instead, matching that semantics.
"""

from __future__ import annotations

import subprocess
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager

from eden.sandboxes.errors import ContainerStartTimeout


@contextmanager
def container_start_deadline(*, binary: str, timeout: float) -> Iterator[Callable[[], float]]:
    """Yield a ``remaining()`` callable bounding a docker/podman ``create()``.

    Raises ``ContainerStartTimeout`` when the shared budget is exhausted
    (checked each time ``remaining()`` is called) or when a wrapped
    ``subprocess.run(timeout=remaining())`` call itself times out.
    """
    deadline = time.monotonic() + timeout

    def _remaining() -> float:
        left = deadline - time.monotonic()
        if left <= 0:
            raise ContainerStartTimeout(binary=binary, timeout=timeout)
        return left

    try:
        yield _remaining
    except subprocess.TimeoutExpired as exc:
        raise ContainerStartTimeout(binary=binary, timeout=timeout) from exc


__all__ = ["container_start_deadline"]
