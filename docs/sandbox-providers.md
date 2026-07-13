# Sandbox providers

Eden ships seven sandbox providers covering local, isolated, cloud, and microVM execution. Each is a `provider()` factory that returns a `SandboxProvider` instance to pass into [`run(sandbox=...)`](python-api.md#run).

---

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

```python
from eden.sandboxes.daytona import provider as daytona_provider

run(..., sandbox=daytona_provider())
```

### Signature

```python
def provider(
    *,
    image: str = "ubuntu:24.04",
    api_key: str | None = None,
    organization_id: str | None = None,
    base_url: str | None = None,
    env: Mapping[str, str] | None = None,
    timeout: float = 60.0,
) -> SandboxProvider: ...
```

- `image` — container image used by the Daytona sandbox. Defaults to `ubuntu:24.04`.
- `api_key` — Daytona API key. Falls back to the `DAYTONA_API_KEY` env var. Required at sandbox-create time.
- `organization_id` — set the `X-Daytona-Organization-ID` header. Falls back to `DAYTONA_ORGANIZATION_ID`.
- `base_url` — override the API endpoint. Falls back to `DAYTONA_API_URL`. Defaults to `https://api.daytona.io`.
- `env` — environment variables forwarded to the sandbox at create time (merged with `CreateOptions.env` from the orchestrator).
- `timeout` — per-request HTTP timeout in seconds. Default `60.0`.

`ProviderUnavailable` is raised at `create()` time (not at factory time) when no API key is found — this lets you import the factory without credentials in scope.

### What it does

Provisions a Daytona cloud sandbox via REST (`POST /api/sandbox`), uploads the host worktree contents base64-encoded, and snapshots the remote tree as the baseline. Each `handle.exec(cmd)` is `POST /toolbox/<id>/process/execute`. `finalize(target)` re-snapshots remotely (via `find ... -exec sha256sum`), pulls each changed file, and patches the host worktree.

### When to use

- Burstable cloud capacity where a single host machine isn't enough.
- Cross-region/multi-region testing where the agent should run far from your dev box.
- Workloads that need a heavier image than your laptop can host.

### When not to use

- Latency-sensitive iteration loops. Every `exec` is a REST round-trip; tight loops are noticeably slower than local providers.
- Environments where outbound HTTPS to `api.daytona.io` (or your override) is blocked.

See [ADR 0001 — Finalizing vs. direct handles](adr/0001-finalizing-vs-direct-handles.md) for the patch-sync rationale.

## `vercel`

```python
from eden.sandboxes.vercel import provider as vercel_provider

run(..., sandbox=vercel_provider())
```

### Signature

```python
def provider(
    *,
    runtime: str = "node24",
    access_token: str | None = None,
    team_id: str | None = None,
    base_url: str | None = None,
    env: Mapping[str, str] | None = None,
    timeout: float = 60.0,
) -> SandboxProvider: ...
```

- `runtime` — Vercel sandbox runtime label. Defaults to `node24`.
- `access_token` — Vercel API token. Falls back to `VERCEL_TOKEN`. Required at sandbox-create time.
- `team_id` — sent as `?teamId=…` on every request. Falls back to `VERCEL_TEAM_ID`.
- `base_url` — override the API endpoint. Falls back to `VERCEL_API_URL`. Defaults to `https://api.vercel.com`.
- `env` — environment variables forwarded to the sandbox at create time.
- `timeout` — per-request HTTP timeout in seconds. Default `60.0`.

`ProviderUnavailable` is raised at `create()` time when no `access_token` is found.

### What it does

Provisions a Vercel sandbox via `POST /v1/sandboxes`, uploads the worktree base64-encoded, snapshots the baseline, and runs each `exec(cmd)` as `POST /v1/sandboxes/<id>/exec`. `finalize(target)` follows the same diff/pull/apply flow as `daytona`.

### When to use

- Vercel-native workflows where the team already has a Vercel token in scope.
- Same burstable-cloud reasoning as `daytona`.

### When not to use

- Latency-sensitive iteration loops (same REST cost as `daytona`).
- Environments where outbound HTTPS to `api.vercel.com` (or your override) is blocked.

## `forkd`

```python
from eden.sandboxes.forkd import provider as forkd_provider

run(..., sandbox=forkd_provider(snapshot="py-base"))
```

Requires the optional `forkd` dependency:

```bash
pip install eden-agent[forkd]
```

[forkd](https://github.com/deeplethe/forkd) is a Firecracker-based microVM "fork from warm parent" runtime for AI-agent workloads. It boots a parent VM once with your runtime warmed (interpreter, dependencies, models), then forks isolated children from that snapshot in milliseconds. This provider drives it through forkd's E2B-compatible Python SDK.

### Signature

```python
def provider(
    *,
    snapshot: str | None = None,
    env: Mapping[str, str] | None = None,
    timeout: float = 60.0,
    sandbox_factory: Callable[[], object] | None = None,
) -> SandboxProvider: ...
```

- `snapshot` — warm-parent snapshot tag children fork from. Passed to the SDK as `Sandbox(template=snapshot)`. `None` uses the SDK's default sandbox.
- `env` — environment variables forwarded into every command the agent runs (merged with `CreateOptions.env` from the orchestrator).
- `timeout` — default per-command timeout in seconds. Default `60.0`.
- `sandbox_factory` — escape hatch called with no arguments to construct the SDK sandbox, bypassing the default `Sandbox(template=...)` path. Use it to point at a non-default controller, set memory limits, or fork from a live checkpoint — anything the forkd SDK exposes that this thin wrapper does not.

`ProviderUnavailable` is raised at `create()` time (not factory time) when the `forkd` SDK is not importable, so you can import the factory on hosts without forkd installed.

### What it does

Spawns a child microVM from `snapshot` via the SDK, uploads the host worktree base64-encoded over `commands.run`, and snapshots the in-guest tree as the baseline. Each `handle.exec(cmd)` is `sandbox.commands.run(cmd, ...)`. `finalize(target)` re-snapshots the guest (via `find ... -exec sha256sum`), pulls each changed file, and patches the host worktree — the same diff/pull/apply flow as `daytona` and `vercel`.

### When to use

- High fan-out workloads: one warm parent amortizes interpreter/dependency/model load across many children, so spawning the Nth sandbox is near-instant.
- Strong KVM isolation without a container daemon, on Linux infrastructure you control.

### When not to use

- macOS or Windows hosts. forkd requires Linux ≥ 5.7 with KVM and `vm.unprivileged_userfaultfd=1`; the SDK is imported lazily so the module loads anywhere, but `create()` will fail off-Linux.
- Latency-sensitive single-shot runs where the warm-parent advantage doesn't apply.

See [ADR 0001 — Finalizing vs. direct handles](adr/0001-finalizing-vs-direct-handles.md) for the patch-sync rationale.

## See also

- [Custom providers](custom-providers.md) — implementing your own `SandboxProvider` and `IsolatedSandboxHandle`.
- [Sandbox provider usage](sandbox-provider-usage.md) — provider selection flowchart and import examples.
- [Configuration](configuration.md) — the env vars each cloud provider falls back to.
- [Python API: `Mount`, `BranchStrategy`, `FinalizeResult`](python-api.md#configuration-types) — provider-agnostic types.
- [How it works](how-it-works.md) — when `finalize()` runs and how the orchestrator detects bind-mount vs isolated handles.
