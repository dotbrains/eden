"""Mount argv and in-container parent setup for Docker/Podman providers."""

from __future__ import annotations

import re
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from eden.providers._types import Mount
from eden.sandboxes.errors import ContainerStartFailed, MountConfigError

SelinuxLabel = Literal["z", "Z"]

SANDBOX_WORKDIR: Path = Path("/workspace")
"""Default in-container worktree path used for relative sandbox mount targets."""

SANDBOX_HOMEDIR: Path = Path("/home/agent")
"""Default in-container home directory used by tilde-expansion."""


def _expand_sandbox_tilde(
    sandbox: Path,
    *,
    sandbox_homedir: Path | None,
    sandbox_workdir: Path = SANDBOX_WORKDIR,
) -> Path:
    parts = sandbox.parts
    if parts and parts[0] == "~":
        if sandbox_homedir is None:
            raise ValueError(
                f"sandbox path {sandbox.as_posix()!r} starts with ~ but provider has "
                "no sandbox_homedir; pass an absolute sandbox path or use a provider "
                "that defines a homedir"
            )
        rest = parts[1:]
        return sandbox_homedir.joinpath(*rest) if rest else sandbox_homedir
    if not sandbox.is_absolute():
        return sandbox_workdir / sandbox
    return sandbox


def _mount_spec(
    *,
    host: Path,
    sandbox: Path,
    read_only: bool,
    selinux: SelinuxLabel | None,
    sandbox_homedir: Path | None = None,
) -> str:
    expanded = _expand_sandbox_tilde(sandbox, sandbox_homedir=sandbox_homedir)
    spec = f"{host}:{expanded.as_posix()}"
    opts: list[str] = []
    if read_only:
        opts.append("ro")
    if selinux is not None:
        opts.append(selinux)
    if opts:
        spec += ":" + ",".join(opts)
    return spec


def _is_windows_host_path(path: Path) -> bool:
    raw = str(path)
    return bool(re.match(r"^[A-Za-z]:[\\/]", raw)) or "\\" in raw


def _mount_argv(
    *,
    host: Path,
    sandbox: Path,
    read_only: bool,
    selinux: SelinuxLabel | None,
    sandbox_homedir: Path | None = None,
) -> list[str]:
    expanded = _expand_sandbox_tilde(sandbox, sandbox_homedir=sandbox_homedir)
    if _is_windows_host_path(host):
        source = str(host).replace("\\", "/")
        spec = f"type=bind,source={source},target={expanded.as_posix()}"
        if read_only:
            spec += ",readonly"
        return ["--mount", spec]
    return [
        "-v",
        _mount_spec(
            host=host,
            sandbox=sandbox,
            read_only=read_only,
            selinux=selinux,
            sandbox_homedir=sandbox_homedir,
        ),
    ]


def _file_mount_parents(mounts: list[Mount], *, sandbox_homedir: Path) -> list[Path]:
    seen: list[Path] = []
    for m in mounts:
        if not m.host.is_file():
            continue
        expanded = _expand_sandbox_tilde(m.sandbox, sandbox_homedir=sandbox_homedir)
        parent = expanded.parent
        if parent == sandbox_homedir:
            continue
        try:
            parent.relative_to(sandbox_homedir)
        except ValueError as exc:
            raise MountConfigError(
                sandbox_path=expanded.as_posix(),
                parent=parent.as_posix(),
                sandbox_homedir=sandbox_homedir.as_posix(),
            ) from exc
        if parent in seen:
            continue
        seen.append(parent)
    return seen


def _ensure_mount_parents(
    *,
    binary: str,
    container_id: str,
    parents: list[Path],
    uid: int,
    gid: int,
    remaining: Callable[[], float] | None = None,
) -> None:
    for parent in parents:
        proc = subprocess.run(
            [
                binary,
                "exec",
                "--user",
                "0:0",
                container_id,
                "sh",
                "-c",
                'mkdir -p "$1" && chown "$2:$3" "$1"',
                "sh",
                parent.as_posix(),
                str(uid),
                str(gid),
            ],
            capture_output=True,
            text=True,
            timeout=remaining() if remaining is not None else None,
        )
        if proc.returncode != 0:
            raise ContainerStartFailed(
                image=container_id,
                exit_code=proc.returncode,
                stderr=(
                    f"failed to prepare mount parent {parent.as_posix()!r}: {proc.stderr.strip()}"
                ),
            )


__all__ = [
    "SANDBOX_HOMEDIR",
    "SANDBOX_WORKDIR",
    "SelinuxLabel",
    "_ensure_mount_parents",
    "_expand_sandbox_tilde",
    "_file_mount_parents",
    "_is_windows_host_path",
    "_mount_argv",
    "_mount_spec",
]
