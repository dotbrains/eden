"""Snapshot command and parser helpers for remote sandbox sync."""

from __future__ import annotations

import shlex
from pathlib import Path


def path_arg(path: Path, *, quote_paths: bool) -> str:
    raw = path.as_posix()
    return shlex.quote(raw) if quote_paths else raw


def snapshot_command(root: Path, *, quote_root: bool = False) -> str:
    root_arg = path_arg(root, quote_paths=quote_root)
    return (
        f"cd {root_arg} && "
        "find . -type f "
        "-not -path './.git/*' -not -path './.eden/*' "
        "-exec sha256sum {} + 2>/dev/null"
    )


def parse_sha256sum_snapshot(stdout: str) -> dict[Path, str]:
    out: dict[Path, str] = {}
    for line in stdout.splitlines():
        if not line.strip():
            continue
        try:
            hex_digest, rest = line.split(maxsplit=1)
        except ValueError:
            continue
        rel = rest.strip()
        if rel.startswith("./"):
            rel = rel[2:]
        out[Path(rel)] = hex_digest
    return out


__all__ = ["parse_sha256sum_snapshot", "path_arg", "snapshot_command"]
