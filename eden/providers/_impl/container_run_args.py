"""Pure argv/name helpers for docker/podman sandbox creation."""

from __future__ import annotations

import re
import secrets
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from eden.providers._impl.container_mounts import SANDBOX_HOMEDIR, SelinuxLabel, _mount_argv
from eden.providers._types import Mount

_NAME_RE = re.compile(r"[^a-z0-9-]+")
_IMAGE_TAG_RE = re.compile(r"[^a-z0-9_.-]+")


def default_image_name(repo_path: Path) -> str:
    repo_name = repo_path.name.lower()
    tag = _IMAGE_TAG_RE.sub("-", repo_name).strip("-")
    return f"eden:{tag or 'local'}"


def build_mount_map(
    *,
    worktree_path: Path,
    opts_mounts: tuple[Mount, ...],
    provider_mounts: tuple[Mount, ...],
) -> dict[Path, Mount]:
    # Mount precedence: implicit /workspace, then opts.mounts, then
    # provider_mounts (last write wins on sandbox-path collision).
    mount_map: dict[Path, Mount] = {
        Path("/workspace"): Mount(host=worktree_path, sandbox=Path("/workspace"))
    }
    for mount in opts_mounts:
        mount_map[mount.sandbox] = _expand_host_path(mount)
    for mount in provider_mounts:
        mount_map[mount.sandbox] = _expand_host_path(mount)
    return mount_map


def _expand_host_path(mount: Mount) -> Mount:
    return Mount(host=mount.host.expanduser(), sandbox=mount.sandbox, read_only=mount.read_only)


def container_name(*, branch: str, name_hint: str | None) -> str:
    suffix = secrets.token_hex(4)
    seed = name_hint or branch
    return f"eden-{_sanitize_container_seed(seed)}-{suffix}"[:63]


def build_run_argv(
    *,
    binary: Literal["docker", "podman"],
    container_name: str,
    uid: int,
    gid: int,
    mounts: Mapping[Path, Mount],
    env: Mapping[str, str],
    networks: tuple[str, ...],
    cpus: float | None,
    userns: Literal["keep-id"] | None,
    devices: tuple[str, ...],
    groups: tuple[str | int, ...],
    image: str,
    selinux_label: SelinuxLabel | None,
) -> list[str]:
    argv: list[str] = [
        binary,
        "run",
        "-d",
        "--rm",
        "-i",
        "--name",
        container_name,
        "--user",
        f"{uid}:{gid}",
        "--entrypoint",
        "sleep",
    ]
    for mount in mounts.values():
        argv.extend(
            _mount_argv(
                host=mount.host,
                sandbox=mount.sandbox,
                read_only=mount.read_only,
                selinux=selinux_label,
                sandbox_homedir=SANDBOX_HOMEDIR,
            )
        )
    for key, value in env.items():
        argv.extend(["-e", f"{key}={value}"])
    for network_name in networks:
        argv.extend(["--network", network_name])
    if cpus is not None:
        argv.extend(["--cpus", str(cpus)])
    if binary == "podman" and userns == "keep-id":
        argv.append(f"--userns=keep-id:uid={uid},gid={gid}")
    for device in devices:
        argv.extend(["--device", device])
    for group in groups:
        argv.extend(["--group-add", str(group)])
    argv.extend([image, "infinity"])
    return argv


def _sanitize_container_seed(seed: str) -> str:
    out = _NAME_RE.sub("-", seed.lower()).strip("-")
    return out or "eden"


__all__ = [
    "build_mount_map",
    "build_run_argv",
    "container_name",
    "default_image_name",
]
