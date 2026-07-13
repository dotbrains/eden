# Cloud and MicroVM Sandbox Providers

Detailed reference for Eden's REST-backed cloud providers and forkd microVM provider. See [Sandbox providers](sandbox-providers.md) for the matrix and local provider details.

---

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

- [Sandbox providers](sandbox-providers.md) — provider matrix and local provider details.
- [Sandbox provider usage](sandbox-provider-usage.md) — provider selection flowchart and import examples.
- [Configuration](configuration.md) — environment variables for cloud providers.
