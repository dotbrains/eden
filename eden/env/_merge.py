"""Layered env merge with collision detection."""

from __future__ import annotations

from collections.abc import Mapping

from eden.errors import EnvMergeError


def merge_env(*layers: Mapping[str, str]) -> dict[str, str]:
    """Merge layers left-to-right; collisions on differing values raise EnvMergeError.

    Same-key/same-value collisions are idempotent (no error). Disjoint keys union.
    """
    out: dict[str, str] = {}
    for layer in layers:
        for key, value in layer.items():
            if key in out and out[key] != value:
                raise EnvMergeError(
                    message=f"env key {key!r} set to conflicting values "
                    f"({out[key]!r} vs {value!r})",
                    hint=f"rename one of the {key!r} settings or set them equal",
                )
            out[key] = value
    return out
