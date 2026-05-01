"""docker provider: run commands inside a long-lived docker container."""

from __future__ import annotations

import re
import secrets
import shutil
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

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
    ProviderUnavailable,
)

_NAME_RE = re.compile(r"[^a-z0-9-]+")


def _sanitize_container_seed(s: str) -> str:
    out = _NAME_RE.sub("-", s.lower()).strip("-")
    return out or "eden"


@dataclass
class _DockerHandle:
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
        argv: list[str] = ["docker", "exec", "-i"]
        if cwd is not None:
            argv.extend(["-w", str(cwd)])
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
            ["docker", "cp", str(host), f"{self.container_id}:{sandbox}"],
            check=True,
            capture_output=True,
            text=True,
        )

    def copy_file_out(self, sandbox: Path, host: Path) -> None:
        subprocess.run(
            ["docker", "cp", f"{self.container_id}:{sandbox}", str(host)],
            check=True,
            capture_output=True,
            text=True,
        )

    def close(self) -> None:
        proc = subprocess.run(
            ["docker", "kill", self.container_id],
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


def provider(
    *,
    image: str,
    mounts: tuple[Mount, ...] | None = None,
    env: Mapping[str, str] | None = None,
    network: str | None = None,
) -> SandboxProvider:
    provider_mounts: tuple[Mount, ...] = mounts or ()
    provider_env: dict[str, str] = dict(env) if env else {}

    def _create(opts: CreateOptions) -> BindMountSandboxHandle:
        if not shutil.which("docker"):
            raise ProviderUnavailable(provider="docker", binary="docker")

        inspect = subprocess.run(
            ["docker", "image", "inspect", image],
            capture_output=True,
            text=True,
        )
        if inspect.returncode != 0:
            raise ImageNotFound(image=image, stderr=inspect.stderr)

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
            "docker",
            "run",
            "-d",
            "--rm",
            "-i",
            "--name",
            container_name,
            "--entrypoint",
            "sleep",
        ]
        for m in mount_map.values():
            spec = f"{m.host}:{m.sandbox}"
            if m.read_only:
                spec += ":ro"
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
        return _DockerHandle(
            container_id=container_id,
            worktree_path=Path("/workspace"),
            host_worktree_path=opts.worktree_path,
        )

    return make_bind_mount_provider(name="docker", create=_create)


__all__ = ["provider"]
