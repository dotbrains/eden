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

Before user `sandbox.on_sandbox_ready` hooks run, Eden configures Git inside real sandboxes. It marks the sandbox worktree as a global `safe.directory` entry when missing, normalizing path separators so repeated Windows runs do not accumulate duplicates, and copies the host repo's `user.name` / `user.email` into sandbox-global Git config when available. This keeps bind-mounted repos usable when file ownership differs and lets agents commit without manual Git setup. `no_sandbox` is skipped so Eden does not mutate the user's host-global Git config.

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

Runs commands directly on the host via `subprocess` with `shell=True`, using the worktree path as the default `cwd`. `kind` is `"none"`. `env` values are merged into sandbox exec environments, and per-call `env` overrides them. `max_output_tail_chars` bounds the stdout/stderr retained in `ExecResult` for streamed exec calls; live `on_line` callbacks still receive every line. Interactive no-sandbox sessions also use shell resolution on Windows so npm-style `.cmd` / `.ps1` agent wrappers on `PATH` can launch.

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

Moved to [Container sandbox providers](container-sandbox-providers.md#docker).

## `podman`

Moved to [Container sandbox providers](container-sandbox-providers.md#podman).

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

Moved to [MicroVM sandbox providers](microvm-sandbox-providers.md#forkd).

## See also

- [Custom providers](custom-providers.md) — implementing your own `SandboxProvider` and `IsolatedSandboxHandle`.
- [Container sandbox providers](container-sandbox-providers.md) — Docker and Podman details.
- [Cloud sandbox providers](cloud-sandbox-providers.md) — Daytona and Vercel details.
- [MicroVM sandbox providers](microvm-sandbox-providers.md) — forkd details.
- [Sandbox provider usage](sandbox-provider-usage.md) — provider selection flowchart and import examples.
- [Configuration](configuration.md) — the env vars each cloud provider falls back to.
- [Python API: `Mount`, `BranchStrategy`, `FinalizeResult`](python-api.md#configuration-types) — provider-agnostic types.
- [How it works](how-it-works.md) — when `finalize()` runs and how the orchestrator detects bind-mount vs isolated handles.
