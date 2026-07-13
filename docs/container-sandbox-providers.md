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
  [`Mount`](python-api.md#mount). `Mount.sandbox` paths starting with `~`
  expand to `/home/agent`; relative paths resolve under `/workspace`.
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

```python
from eden.sandboxes.podman import provider as podman_provider

run(..., sandbox=podman_provider(image="my-image:latest"))
```

### Signature

Identical to `docker` plus `userns`:

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
    userns: Literal["keep-id"] | None = "keep-id",
    max_output_tail_chars: int = 64 * 1024,
) -> SandboxProvider: ...
```

### What it does

Same lifecycle as `docker`, but invokes `podman` instead. It is rootless by
default and suitable for environments without a privileged daemon.

Mount formatting, Windows-path handling, SELinux relabeling, and single-file
mount parent validation match Docker. By default Eden also passes
`--userns=keep-id:uid=<uid>,gid=<gid>` so rootless Podman maps the host user to
the configured in-container user without runtime `chown`. Pass `userns=None`
for rootful Podman or a custom namespace setup.

### When to use

- Same use cases as `docker`, but on hosts where Docker is unavailable or
  rootless isolation is preferred.
- CI environments that ship `podman`, such as RHEL-family runners.

### When not to use

- macOS hosts without a Podman machine. Eden does not auto-provision the VM;
  configure it yourself first.

## See also

- [Sandbox providers](sandbox-providers.md) — provider matrix and local
  filesystem providers.
- [Sandbox and worktree errors](sandbox-worktree-errors.md) — container startup
  and mount errors.
- [ADR 0005](adr/0005-container-ux-hygiene.md) — UID, SELinux, and tilde mount
  behavior.
