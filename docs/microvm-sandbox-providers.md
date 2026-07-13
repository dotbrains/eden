# MicroVM Sandbox Providers

Detailed reference for Eden's microVM provider. See
[Sandbox providers](sandbox-providers.md) for the full provider matrix and
[Cloud sandbox providers](cloud-sandbox-providers.md) for REST-backed cloud
providers.

## `forkd`

```python
from eden.sandboxes.forkd import provider as forkd_provider

run(..., sandbox=forkd_provider(snapshot="py-base"))
```

Requires the optional `forkd` dependency:

```bash
pip install eden-agent[forkd]
```

[forkd](https://github.com/deeplethe/forkd) is a Firecracker-based microVM "fork
from warm parent" runtime for AI-agent workloads. It boots a parent VM once with
your runtime warmed (interpreter, dependencies, models), then forks isolated
children from that snapshot in milliseconds. This provider drives it through
forkd's E2B-compatible Python SDK.

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

`ProviderUnavailable` is raised at `create()` time (not factory time) when the
`forkd` SDK is not importable, so you can import the factory on hosts without
forkd installed.

### What it does

Spawns a child microVM from `snapshot` via the SDK, uploads the host worktree
base64-encoded over `commands.run`, and snapshots the in-guest tree as the
baseline. Each `handle.exec(cmd)` is `sandbox.commands.run(cmd, ...)`.
`finalize(target)` re-snapshots the guest (via `find ... -exec sha256sum`),
pulls each changed file, and patches the host worktree — the same
diff/pull/apply flow as `daytona` and `vercel`.

### When to use

- High fan-out workloads: one warm parent amortizes interpreter/dependency/model load across many children, so spawning the Nth sandbox is near-instant.
- Strong KVM isolation without a container daemon, on Linux infrastructure you control.

### When not to use

- macOS or Windows hosts. forkd requires Linux ≥ 5.7 with KVM and `vm.unprivileged_userfaultfd=1`; the SDK is imported lazily so the module loads anywhere, but `create()` will fail off-Linux.
- Latency-sensitive single-shot runs where the warm-parent advantage doesn't apply.

See [ADR 0001 — Finalizing vs. direct handles](adr/0001-finalizing-vs-direct-handles.md)
for the patch-sync rationale.
