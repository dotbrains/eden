"""Container image inspection helpers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from eden.sandboxes.errors import ImageNotFound, ImageUidMismatch


class ImageInspectResult(Protocol):
    returncode: int
    stdout: str
    stderr: str


ImageInspectRunner = Callable[..., ImageInspectResult]


def verify_image(
    *,
    binary: str,
    image: str,
    expected_uid: int,
    run: ImageInspectRunner,
    remaining: Callable[[], float],
) -> None:
    """Confirm ``image`` exists locally and its UID matches, or raise.

    Combines the existence pre-flight (``ImageNotFound``) and
    ``check_image_uid``'s numeric-UID check under the docker/podman
    ``create()`` sequence's shared deadline (see ``container_deadline.py``).
    """
    proc = run(
        [binary, "image", "inspect", image], capture_output=True, text=True, timeout=remaining()
    )
    if proc.returncode != 0:
        raise ImageNotFound(image=image, stderr=proc.stderr)
    check_image_uid(
        binary=binary, image=image, expected_uid=expected_uid, run=run, timeout=remaining()
    )


def check_image_uid(
    *,
    binary: str,
    image: str,
    expected_uid: int,
    run: ImageInspectRunner,
    timeout: float | None = None,
) -> None:
    """Verify the image's USER UID matches the expected one.

    Skips silently when the image has no USER directive or a non-numeric one
    (e.g. ``USER agent``) — in those cases UID is set at runtime via ``--user``.
    Raises ``ImageUidMismatch`` for a numeric mismatch. ``timeout`` bounds the
    inspect call; callers building the docker/podman create() sequence pass
    the remaining share of a shared deadline (see ``container_deadline.py``).
    """
    proc = run(
        [binary, "image", "inspect", image, "--format", "{{.Config.User}}"],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        return  # ImageNotFound is raised by the caller's earlier inspect.
    raw = (proc.stdout or "").strip()
    if not raw:
        return
    uid_part = raw.split(":", 1)[0]
    try:
        image_uid = int(uid_part)
    except ValueError:
        return
    if image_uid != expected_uid:
        raise ImageUidMismatch(
            image=image,
            image_uid=image_uid,
            expected_uid=expected_uid,
        )


__all__ = ["check_image_uid", "verify_image"]
