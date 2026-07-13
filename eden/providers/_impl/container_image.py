"""Container image inspection helpers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from eden.sandboxes.errors import ImageUidMismatch


class ImageInspectResult(Protocol):
    returncode: int
    stdout: str


ImageInspectRunner = Callable[..., ImageInspectResult]


def check_image_uid(
    *,
    binary: str,
    image: str,
    expected_uid: int,
    run: ImageInspectRunner,
) -> None:
    """Verify the image's USER UID matches the expected one.

    Skips silently when the image has no USER directive or a non-numeric one
    (e.g. ``USER agent``) — in those cases UID is set at runtime via ``--user``.
    Raises ``ImageUidMismatch`` for a numeric mismatch.
    """
    proc = run(
        [binary, "image", "inspect", image, "--format", "{{.Config.User}}"],
        capture_output=True,
        text=True,
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


__all__ = ["check_image_uid"]
