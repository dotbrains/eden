"""Shared container-runtime provider: docker / podman bind-mount sandboxes."""

from __future__ import annotations

import os
import re
import secrets
import shutil
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from eden.providers._helpers import make_bind_mount_provider
from eden.providers._protocols import (
    BindMountSandboxHandle,
    SandboxProvider,
)
from eden.providers._types import CreateOptions, ExecResult, Mount
from eden.sandboxes._exec import stream_exec
from eden.sandboxes.errors import (
    ContainerStartFailed,
    ImageNotFound,
    ImageUidMismatch,
    ProviderUnavailable,
)

_NAME_RE = re.compile(r"[^a-z0-9-]+")


def _sanitize_container_seed(s: str) -> str:
    out = _NAME_RE.sub("-", s.lower()).strip("-")
    return out or "eden"


@dataclass
class _ContainerHandle:
    binary: str
    container_id: str
    worktree_path: Path
    host_worktree_path: Path

    def exec(
        self,
        cmd: str,
        *,
        on_line: Callable[[str], None] | None = None,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> ExecResult:
        argv: list[str] = [self.binary, "exec", "-i"]
        if cwd is not None:
            argv.extend(["-w", cwd.as_posix()])
        if env:
            for k, v in env.items():
                argv.extend(["-e", f"{k}={v}"])
        argv.extend([self.container_id, "/bin/sh", "-c", cmd])
        return stream_exec(
            argv,
            cmd_for_error=cmd,
            shell=False,
            on_line=on_line,
            timeout=timeout,
        )

    def copy_file_in(self, host: Path, sandbox: Path) -> None:
        subprocess.run(
            [self.binary, "cp", str(host), f"{self.container_id}:{sandbox.as_posix()}"],
            check=True,
            capture_output=True,
            text=True,
        )

    def copy_file_out(self, sandbox: Path, host: Path) -> None:
        subprocess.run(
            [self.binary, "cp", f"{self.container_id}:{sandbox.as_posix()}", str(host)],
            check=True,
            capture_output=True,
            text=True,
        )

    def close(self) -> None:
        proc = subprocess.run(
            [self.binary, "kill", self.container_id],
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0:
            return None
        if "no such container" in (proc.stderr or "").lower():
            return None
        # Other errors during cleanup: don't propagate; --rm will still
        # GC if the container later exits, and re-raising would mask
        # original errors thrown from the user code path.
        return None


def _check_image_uid(
    *, binary: str, image: str, expected_uid: int
) -> None:
    """Verify the image's USER UID matches the expected one.

    Skips silently when the image has no USER directive or a non-numeric one
    (e.g. ``USER agent``) — in those cases UID is set at runtime via ``--user``.
    Raises ``ImageUidMismatch`` for a numeric mismatch.
    """
    proc = subprocess.run(
        [binary, "image", "inspect", image, "--format", "{{.Config.User}}"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return  # ImageNotFound is raised by the caller's earlier inspect
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


def _host_uid() -> int:
    """Return the host's UID, or 1000 on platforms without ``getuid``."""
    getuid = getattr(os, "getuid", None)
    return getuid() if getuid is not None else 1000


def _host_gid() -> int:
    """Return the host's GID, or 1000 on platforms without ``getgid``."""
    getgid = getattr(os, "getgid", None)
    return getgid() if getgid is not None else 1000


SelinuxLabel = Literal["z", "Z"]


def _expand_sandbox_tilde(sandbox: Path, *, sandbox_homedir: Path | None) -> Path:
    """Expand a leading ``~`` in a sandbox-side path using ``sandbox_homedir``.

    Raises ``ValueError`` if ``sandbox`` starts with ``~`` but the provider has
    no ``sandbox_homedir``. Paths without a leading ``~`` pass through unchanged.
    """
    parts = sandbox.parts
    if not parts or parts[0] != "~":
        return sandbox
    if sandbox_homedir is None:
        raise ValueError(
            f"sandbox path {sandbox.as_posix()!r} starts with ~ but provider has "
            "no sandbox_homedir; pass an absolute sandbox path or use a provider "
            "that defines a homedir"
        )
    rest = parts[1:]
    return sandbox_homedir.joinpath(*rest) if rest else sandbox_homedir


def _mount_spec(
    *,
    host: Path,
    sandbox: Path,
    read_only: bool,
    selinux: SelinuxLabel | None,
    sandbox_homedir: Path | None = None,
) -> str:
    """Build a bind-mount spec string.

    Combines ``read_only`` and SELinux relabel suffixes into the trailing
    options block expected by ``docker run -v`` / ``podman run -v``:
    ``host:sandbox[:opt1,opt2...]``. Expands a leading ``~`` in ``sandbox``
    using ``sandbox_homedir`` (e.g. ``Path("/home/agent")``).
    """
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


# Default in-container home directory used by tilde-expansion. Matches the
# ``agent`` user created by eden's blank-template Dockerfile.
SANDBOX_HOMEDIR: Path = Path("/home/agent")


def make_container_provider(
    *,
    binary: Literal["docker", "podman"],
    image: str,
    mounts: tuple[Mount, ...] | None = None,
    env: Mapping[str, str] | None = None,
    network: str | None = None,
    container_uid: int | None = None,
    container_gid: int | None = None,
    selinux_label: SelinuxLabel | None = "z",
) -> SandboxProvider:
    """Build a bind-mount SandboxProvider backed by ``<binary> run``.

    Identical argv shape for docker and podman; the binary name is threaded
    through every subprocess call (run, exec, cp, kill).

    ``container_uid`` / ``container_gid`` set the in-container user. When
    ``None``, defaults to the host's UID/GID so files written into bind-mounted
    paths land with the host user as owner. A pre-flight ``image inspect``
    raises ``ImageUidMismatch`` if the image was built for a different UID.

    ``selinux_label`` appends an SELinux relabel suffix to every bind mount.
    Default ``"z"`` shares the label across containers; ``"Z"`` makes it
    container-private; ``None`` disables relabeling (use on hosts where SELinux
    is not enforced or relabel would conflict). The label is harmless on
    non-SELinux hosts (Docker / Podman ignore the suffix).
    """
    provider_mounts: tuple[Mount, ...] = mounts or ()
    provider_env: dict[str, str] = dict(env) if env else {}
    effective_uid: int = container_uid if container_uid is not None else _host_uid()
    effective_gid: int = container_gid if container_gid is not None else _host_gid()

    def _create(opts: CreateOptions) -> BindMountSandboxHandle:
        if not shutil.which(binary):
            raise ProviderUnavailable(provider=binary, binary=binary)

        inspect = subprocess.run(
            [binary, "image", "inspect", image],
            capture_output=True,
            text=True,
        )
        if inspect.returncode != 0:
            raise ImageNotFound(image=image, stderr=inspect.stderr)

        _check_image_uid(binary=binary, image=image, expected_uid=effective_uid)

        # Mount precedence: implicit /workspace, then opts.mounts, then
        # provider_mounts (last write wins on sandbox-path collision).
        mount_map: dict[Path, Mount] = {}
        mount_map[Path("/workspace")] = Mount(host=opts.worktree_path, sandbox=Path("/workspace"))
        for m in opts.mounts:
            mount_map[m.sandbox] = m
        for m in provider_mounts:
            mount_map[m.sandbox] = m

        merged_env: dict[str, str] = {**provider_env, **dict(opts.env)}

        suffix = secrets.token_hex(4)
        seed = opts.name_hint or opts.branch
        container_name = f"eden-{_sanitize_container_seed(seed)}-{suffix}"
        container_name = container_name[:63]

        argv: list[str] = [
            binary,
            "run",
            "-d",
            "--rm",
            "-i",
            "--name",
            container_name,
            "--user",
            f"{effective_uid}:{effective_gid}",
            "--entrypoint",
            "sleep",
        ]
        for m in mount_map.values():
            spec = _mount_spec(
                host=m.host,
                sandbox=m.sandbox,
                read_only=m.read_only,
                selinux=selinux_label,
                sandbox_homedir=SANDBOX_HOMEDIR,
            )
            argv.extend(["-v", spec])
        for k, v in merged_env.items():
            argv.extend(["-e", f"{k}={v}"])
        if network:
            argv.extend(["--network", network])
        argv.extend([image, "infinity"])

        run_proc = subprocess.run(argv, capture_output=True, text=True)
        if run_proc.returncode != 0:
            raise ContainerStartFailed(
                image=image,
                exit_code=run_proc.returncode,
                stderr=run_proc.stderr,
            )
        container_id = run_proc.stdout.strip()
        return _ContainerHandle(
            binary=binary,
            container_id=container_id,
            worktree_path=Path("/workspace"),
            host_worktree_path=opts.worktree_path,
        )

    return make_bind_mount_provider(name=binary, create=_create)


__all__ = ["make_container_provider"]
