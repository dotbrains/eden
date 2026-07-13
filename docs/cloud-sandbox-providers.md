# Cloud Sandbox Providers

Detailed reference for Eden's REST-backed cloud providers. See
[Sandbox providers](sandbox-providers.md) for the matrix and local provider
details, and [MicroVM sandbox providers](microvm-sandbox-providers.md) for
`forkd`.

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

Moved to [MicroVM sandbox providers](microvm-sandbox-providers.md#forkd).

## See also

- [Sandbox providers](sandbox-providers.md) — provider matrix and local provider details.
- [Sandbox provider usage](sandbox-provider-usage.md) — provider selection flowchart and import examples.
- [MicroVM sandbox providers](microvm-sandbox-providers.md) — forkd details.
- [Configuration](configuration.md) — environment variables for cloud providers.
