# Sandbox providers

Eden ships seven sandbox providers covering local, isolated, cloud, and microVM execution. Each is a `provider()` factory that returns a `SandboxProvider` instance to pass into [`run(sandbox=...)`](python-api.md#run).

## Provider matrix

| Provider | Kind | Mounts host? | Network? | Side effects on host? | When to use |
|---|---|---|---|---|---|
| `no_sandbox` | bind-mount | yes (worktree path) | yes | yes (changes on host filesystem) | Trusted code, fastest iteration. |
| `docker` | bind-mount | yes (bind mount) | configurable | confined to mount | Untrusted code on Linux/macOS. |
| `podman` | bind-mount | yes (bind mount) | configurable | confined to mount | Same as `docker`, rootless. |
| `isolated` | patch-sync | no (copy + diff) | yes | none until `finalize()` | Strong isolation on a single host. |
| `daytona` | cloud (REST) | no (REST upload) | yes | none until `finalize()` | Burstable cloud capacity. |
| `vercel` | cloud (REST) | no (REST upload) | yes | none until `finalize()` | Vercel-managed sandboxes. |
| `forkd` | microVM (SDK) | no (SDK upload) | yes | none until `finalize()` | Firecracker microVMs, fork-from-warm-snapshot (Linux + KVM). |

Each provider's `kind` (`"none"`, `"bind_mount"`, or `"isolated"`) controls how `create_sandbox` and `run()` resolve the default branch strategy and whether the orchestrator calls `handle.finalize(...)` after the run. See [how-it-works.md](how-it-works.md) for the full lifecycle.

## Choosing a provider

Moved to [Sandbox provider usage](sandbox-provider-usage.md#choosing-a-provider).

## Importing
Moved to [Sandbox provider usage](sandbox-provider-usage.md#importing).

## `no_sandbox`

```python
from eden.sandboxes.no_sandbox import provider as no_sandbox

run(..., sandbox=no_sandbox())
```

### Signature

```python
def provider(
    *,
    env: Mapping[str, str] | None = None,
    max_output_tail_chars: int = 64 * 1024,
) -> SandboxProvider: ...
```

Runs commands directly on the host via `subprocess` with `shell=True`, using the worktree path as the default `cwd`. `kind` is `"none"`. `env` values are merged into sandbox exec environments, and per-call `env` overrides them. `max_output_tail_chars` bounds the stdout/stderr retained in `ExecResult` for streamed exec calls; live `on_line` callbacks still receive every line.

### What it does

Spawns each `exec(cmd)` call as a host shell subprocess. `copy_file_in` / `copy_file_out` are direct `shutil.copy2` calls. There is no isolation: the agent sees your real filesystem, network, and environment.

### When to use

- Trusted code where you want zero overhead.
- Fastest iteration during agent development — no container build, no REST round-trip.
- The default for examples and the `simulated_agent` smoke test.

### When not to use

- Any time the agent could touch files outside the worktree (it can: `shell=True` plus host process means it has your full permissions).
- Any time you need reproducible environment isolation. Use `docker` or `isolated` instead.

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

- `image` — container image (must already be built; the provider does not build). Defaults to `eden:<repo-dir>`, lowercased and sanitized from the host repository directory name.
- `mounts` — extra bind mounts beyond the worktree itself. See [`Mount`](python-api.md#mount). `Mount.sandbox` paths starting with `~` are expanded to `/home/agent` (the default in-container homedir); relative paths are resolved under `/workspace`, so `Mount(sandbox=Path("data"))` mounts at `/workspace/data`. For **file** mounts (host path is a regular file) whose target lives under `/home/agent`, eden runs a one-shot `mkdir -p` + `chown` after container start so the agent user can write into the parent directory; the prep failure surfaces as `ContainerStartFailed` before any user code runs. File mounts whose sandbox-side parent is outside `/home/agent` raise `MountConfigError`; mount the parent directory instead or rebuild the image with that parent pre-created.
- `env` — environment variables propagated into the container.
- `network` — Docker `--network` flag value (e.g. `"host"`, `"none"`) or tuple of values; tuples emit one `--network` flag per entry. `None` keeps Docker's default bridge.
- `container_uid` / `container_gid` — UID/GID passed via `--user`. `None` (default) auto-derives from the host's UID/GID so files written through the bind-mounted worktree land owned by the host user. A pre-flight `docker image inspect` raises `ImageUidMismatch` when the image was built for a different numeric UID; rebuild with `--build-arg AGENT_UID=$(id -u) --build-arg AGENT_GID=$(id -g)` to align them.
- `selinux_label` — bind-mount relabel suffix appended to every `-v` spec. `"z"` (default) shares the label; `"Z"` makes it container-private; `None` disables. Required on SELinux hosts (Fedora, RHEL); harmless elsewhere because Docker / Podman ignore the suffix on non-SELinux systems.
- `devices` — host device specs passed via `--device` (for example `("/dev/kvm",)`).
- `cpus` — CPU limit passed via `--cpus`, including fractional values.
- `groups` — supplementary groups passed via `--group-add`, useful for mounted sockets such as `/var/run/docker.sock`.
- `max_output_tail_chars` — maximum stdout/stderr retained in `ExecResult` for streamed exec calls. Live `on_line` callbacks are not truncated.

Windows-shaped host paths such as `C:\Users\me\.npm` are emitted with Docker/Podman `--mount type=bind,...` instead of `-v`, avoiding drive-letter colon ambiguity. POSIX host paths continue to use `-v` so SELinux relabeling remains available.

### What it does

Creates a long-running container that bind-mounts the worktree path. Each `handle.exec(cmd)` runs as `docker exec` against that container. Reads and writes happen in-place on the host filesystem because the worktree is bind-mounted — no `finalize()` step.

### When to use

- Untrusted code on Linux/macOS where you want process and filesystem isolation but still want fast in-place commits.
- Reproducible base images (Dockerfile pinned to a tag).
- Networked agents that need controlled DNS/proxy via the `network` flag.

### When not to use

- macOS-only Apple Silicon hosts where bind-mount performance matters more than isolation — switch to `no_sandbox` for pure-iteration workloads.
- Environments without a Docker daemon. Use `podman` (rootless) or `isolated` (no daemon).

## `podman`

```python
from eden.sandboxes.podman import provider as podman_provider

run(..., sandbox=podman_provider(image="my-image:latest"))
```

### Signature

Identical to `docker`:

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

Same lifecycle as `docker` but invokes the `podman` binary instead of `docker`. Rootless by default, suitable for environments without a privileged daemon.

Mount formatting, Windows-path handling, SELinux relabeling, and single-file mount parent validation match the Docker provider. By default Eden also passes `--userns=keep-id:uid=<uid>,gid=<gid>` so rootless Podman maps the host user to the configured in-container user without runtime `chown`. Pass `userns=None` for rootful Podman or a custom namespace setup.

### When to use

- Same use cases as `docker`, but on hosts where Docker isn't available or rootless isolation is preferred.
- CI environments that ship `podman` (e.g. RHEL-family runners).

### When not to use

- macOS hosts without a Podman machine. Eden does not auto-provision the VM; configure it yourself first.

## `isolated`

```python
from eden.sandboxes.isolated import provider as isolated_provider

run(..., sandbox=isolated_provider())
```

### Signature

```python
def provider(*, base_dir: Path | None = None) -> SandboxProvider: ...
```

- `base_dir` — root directory under which each run carves a fresh sub-directory. Defaults to `<host_repo>/.eden/isolated/`.

### What it does

Copies the worktree (excluding `.git` and `.eden`) into a fresh tmp directory, snapshots the file hashes as a baseline, then runs the agent there. Each `exec(cmd)` is a host `/bin/sh -c <cmd>` whose `cwd` defaults to the isolated copy. After the run, `finalize(target)` re-snapshots, computes a diff, and patches the host worktree with the changed/added/removed files.

### When to use

- Strong isolation on a single host without containers or daemons — useful for `claude-code`-style agents that you don't want touching `.eden/` or `.git/` directly.
- Local debugging of patch-sync semantics that the cloud providers also use.

### When not to use

- Workloads that run system-level installs you want torn down between iterations. The isolated copy is a plain directory; nothing is rolled back automatically beyond what `finalize()`'s diff produces.

## `daytona`

Moved to [Cloud and microVM sandbox providers](cloud-sandbox-providers.md#daytona).

## `vercel`

Moved to [Cloud and microVM sandbox providers](cloud-sandbox-providers.md#vercel).

## `forkd`

Moved to [Cloud and microVM sandbox providers](cloud-sandbox-providers.md#forkd).

## See also

- [Custom providers](custom-providers.md) — implementing your own `SandboxProvider` and `IsolatedSandboxHandle`.
- [Cloud and microVM sandbox providers](cloud-sandbox-providers.md) — Daytona, Vercel, and forkd details.
- [Sandbox provider usage](sandbox-provider-usage.md) — provider selection flowchart and import examples.
- [Configuration](configuration.md) — the env vars each cloud provider falls back to.
- [Python API: `Mount`, `BranchStrategy`, `FinalizeResult`](python-api.md#configuration-types) — provider-agnostic types.
- [How it works](how-it-works.md) — when `finalize()` runs and how the orchestrator detects bind-mount vs isolated handles.
