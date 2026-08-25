from __future__ import annotations

import shutil
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from eden.providers._helpers import make_bind_mount_provider
from eden.providers._impl.container_deadline import container_start_deadline
from eden.providers._impl.container_git_mount import resolve_git_common_dir
from eden.providers._impl.container_git_mount_windows import merge_windows_git_mounts
from eden.providers._impl.container_handle import ContainerHandle
from eden.providers._impl.container_identity import host_gid, host_uid
from eden.providers._impl.container_image import verify_image
from eden.providers._impl.container_mounts import SelinuxLabel
from eden.providers._impl.container_prepare import prepare_file_mount_parents
from eden.providers._impl.container_run_args import (
    build_mount_map,
    build_run_argv,
    container_name,
    default_image_name,
)
from eden.providers._protocols import (
    BindMountSandboxHandle,
    SandboxProvider,
)
from eden.providers._types import CreateOptions, Mount
from eden.sandboxes.errors import (
    ContainerStartFailed,
    ProviderUnavailable,
)
from eden.streaming._bounded_tail import DEFAULT_MAX_CHARS


def make_container_provider(
    *,
    binary: Literal["docker", "podman"],
    image: str | None = None,
    mounts: tuple[Mount, ...] | None = None,
    env: Mapping[str, str] | None = None,
    network: str | tuple[str, ...] | None = None,
    container_uid: int | None = None,
    container_gid: int | None = None,
    selinux_label: SelinuxLabel | None = "z",
    devices: tuple[str, ...] | None = None,
    cpus: float | None = None,
    groups: tuple[str | int, ...] | None = None,
    userns: Literal["keep-id"] | None = None,
    ports: tuple[int, ...] | None = None,
    max_output_tail_chars: int = DEFAULT_MAX_CHARS,
    create_timeout: float = 120.0,
) -> SandboxProvider:
    """Build a bind-mount provider backed by ``<binary> run``.

    Identical argv shape for docker and podman; the binary name is threaded
    through every subprocess call (run, exec, cp, kill).

    ``image`` defaults to ``eden:<repo-dir>`` using the host repository path
    passed at sandbox creation time.

    ``container_uid`` / ``container_gid`` set the in-container user. When
    ``None``, defaults to the host's UID/GID so files written into bind-mounted
    paths land with the host user as owner. A pre-flight ``image inspect``
    raises ``ImageUidMismatch`` if the image was built for a different UID.

    ``selinux_label`` appends an SELinux relabel suffix to every bind mount.
    Default ``"z"`` shares the label across containers; ``"Z"`` makes it
    container-private; ``None`` disables relabeling (use on hosts where SELinux
    is not enforced or relabel would conflict). The label is harmless on
    non-SELinux hosts (Docker / Podman ignore the suffix).

    ``network`` accepts a single runtime network name or a tuple of names. A
    tuple emits one ``--network`` flag per entry. ``devices`` exposes host
    device specs such as ``"/dev/kvm"`` or ``"/dev/dri:/dev/dri:rwm"`` for GPU
    workloads or KVM nesting. ``cpus`` bounds container CPU usage via
    ``--cpus <value>``.

    ``groups`` adds supplementary groups (``--group-add``), commonly ``("docker",)``.
    ``max_output_tail_chars`` bounds returned stdout/stderr tails for streamed exec.

    ``create_timeout`` bounds the whole container-creation sequence. Raises
    ``ContainerStartTimeout`` on expiry.
    """
    provider_mounts: tuple[Mount, ...] = mounts or ()
    provider_env: dict[str, str] = dict(env) if env else {}
    provider_devices: tuple[str, ...] = devices or ()
    provider_groups: tuple[str | int, ...] = groups or ()
    provider_ports: tuple[int, ...] = ports or ()
    provider_networks: tuple[str, ...] = (
        () if network is None else (network,) if isinstance(network, str) else network
    )
    effective_uid: int = container_uid if container_uid is not None else host_uid()
    effective_gid: int = container_gid if container_gid is not None else host_gid()

    def _create(opts: CreateOptions) -> BindMountSandboxHandle:
        if not shutil.which(binary):
            raise ProviderUnavailable(provider=binary, binary=binary)

        with container_start_deadline(binary=binary, timeout=create_timeout) as remaining:
            resolved_image = image or default_image_name(opts.host_repo_path)
            verify_image(
                binary=binary,
                image=resolved_image,
                expected_uid=effective_uid,
                run=subprocess.run,
                remaining=remaining,
            )

            mount_map = build_mount_map(
                worktree_path=opts.worktree_path,
                opts_mounts=opts.mounts,
                provider_mounts=provider_mounts,
                git_common_dir=resolve_git_common_dir(opts.worktree_path),
            )
            no_prep_mounts = merge_windows_git_mounts(mount_map, opts.worktree_path)
            merged_env: dict[str, str] = {**provider_env, **dict(opts.env)}
            name = container_name(branch=opts.branch, name_hint=opts.name_hint)
            argv = build_run_argv(
                binary=binary,
                container_name=name,
                uid=effective_uid,
                gid=effective_gid,
                mounts=mount_map,
                env=merged_env,
                networks=provider_networks,
                cpus=cpus,
                userns=userns,
                devices=provider_devices,
                groups=provider_groups,
                image=resolved_image,
                selinux_label=selinux_label,
                ports=provider_ports,
            )

            run_proc = subprocess.run(argv, capture_output=True, text=True, timeout=remaining())
            if run_proc.returncode != 0:
                raise ContainerStartFailed(
                    image=resolved_image,
                    exit_code=run_proc.returncode,
                    stderr=run_proc.stderr,
                )
            container_id = run_proc.stdout.strip()

            prepare_file_mount_parents(
                binary=binary,
                container_id=container_id,
                mount_map={s: m for s, m in mount_map.items() if m not in no_prep_mounts},
                uid=effective_uid,
                gid=effective_gid,
                remaining=remaining,
            )

        return ContainerHandle(
            binary=binary,
            container_id=container_id,
            worktree_path=Path("/workspace"),
            host_worktree_path=opts.worktree_path,
            max_output_tail_chars=max_output_tail_chars,
            declared_ports=provider_ports,
        )

    return make_bind_mount_provider(name=binary, create=_create)
