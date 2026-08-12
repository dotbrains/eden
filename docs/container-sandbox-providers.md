# Container sandbox providers

Detailed reference for Eden's Docker and Podman bind-mount providers. See
[Sandbox providers](sandbox-providers.md) for the provider matrix and
[Sandbox provider usage](sandbox-provider-usage.md) for selection guidance.

## `docker`

```python
from eden.sandboxes.docker import provider as docker_provider

run(..., sandbox=docker_provider(image="my-image:latest"))
```

### Signature

```python
def provider(
    *,
    image: str | None = None,
    mounts: tuple[Mount, ...] | None = None,
    env: Mapping[str, str] | None = None,
    network: str | tuple[str, ...] | None = None,
    container_uid: int | None = None,
    container_gid: int | None = None,
    selinux_label: Literal["z", "Z"] | None = "z",
    devices: tuple[str, ...] | None = None,
    cpus: float | None = None,
    groups: tuple[str | int, ...] | None = None,
    max_output_tail_chars: int = 64 * 1024,
) -> SandboxProvider: ...
```

- `image` — container image (must already be built; the provider does not
  build). Defaults to `eden:<repo-dir>`, lowercased and sanitized from the host
  repository directory name.
- `mounts` — extra bind mounts beyond the worktree itself. See
  [`Mount`](python-api.md#mount). `Mount.host` paths starting with `~` expand
  to the host home directory. `Mount.sandbox` paths starting with `~` expand to
  `/home/agent`; relative paths resolve under `/workspace`.
- `env` — environment variables propagated into the container.
- `network` — Docker `--network` value such as `"host"` or `"none"`, or a tuple
  emitted as multiple flags. `None` keeps Docker's default bridge.
- `container_uid` / `container_gid` — UID/GID passed via `--user`. `None`
  auto-derives from the host so bind-mounted writes remain host-owned.
- `selinux_label` — bind-mount relabel suffix (`"z"`, `"Z"`, or `None`).
  Required on SELinux hosts; harmless elsewhere.
- `devices` — host device specs passed via `--device`.
- `cpus` — CPU limit passed via `--cpus`.
- `groups` — supplementary groups passed via `--group-add`.
- `max_output_tail_chars` — stdout/stderr retained in `ExecResult` for streamed
  exec calls. Live callbacks still receive every line.

For file mounts targeting `/home/agent`, Eden creates and owns the parent
directory before user code runs; prep failures surface as
`ContainerStartFailed`. File mounts outside `/home/agent` must target an
existing parent or raise `MountConfigError`.

Windows-shaped host paths such as `C:\Users\me\.npm` use Docker/Podman
`--mount type=bind,...` to avoid drive-letter colon ambiguity. POSIX paths keep
using `-v` so SELinux relabeling remains available.

### What it does

Creates a long-running container that bind-mounts the worktree path. Each
`handle.exec(cmd)` runs as `docker exec` against that container. Reads and
writes happen in-place on the host filesystem, so there is no `finalize()`
step.

When the worktree is a linked worktree (the `merge_to_head`/`named` branch
strategies, the default for this provider), its `.git` is a file pointing at
the main repository's git dir by absolute host path. Eden additionally
bind-mounts that git dir at its own host path (Linux/macOS only — see
[ADR 0016](adr/0016-linked-worktree-git-dir-mount.md)) so `git` commands
resolve inside the container; the `head` strategy needs no extra mount since
its `.git` is already a real directory inside the mounted worktree.

### When to use

- Untrusted code on Linux/macOS where you want process and filesystem isolation
  but still want fast in-place commits.
- Reproducible base images pinned to a tag.
- Networked agents that need controlled DNS/proxy via the `network` flag.

### When not to use

- macOS-only Apple Silicon hosts where bind-mount performance matters more than
  isolation; use `no_sandbox` for pure-iteration workloads.
- Environments without a Docker daemon. Use `podman` or `isolated` instead.

## `podman`

Moved to [Podman sandbox provider](podman-sandbox-provider.md).

Compatibility anchor:

<a id="podman"></a>

Read [Podman sandbox provider](podman-sandbox-provider.md#podman) for the
signature, lifecycle, and host requirements.

## See also

- [Sandbox providers](sandbox-providers.md) — provider matrix and local
  filesystem providers.
- [Podman sandbox provider](podman-sandbox-provider.md) — rootless container
  provider details.
- [Sandbox and worktree errors](sandbox-worktree-errors.md) — container startup
  and mount errors.
- [ADR 0005](adr/0005-container-ux-hygiene.md) — UID, SELinux, and tilde mount
  behavior.
