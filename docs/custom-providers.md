# Custom providers

Implement the `SandboxProvider` Protocol — and one of `BindMountSandboxHandle` or `IsolatedSandboxHandle` for the handle it produces — to plug your own sandbox into `eden.run(sandbox=...)`.

## When to write one

The seven in-tree providers (`no_sandbox`, `docker`, `podman`, `isolated`, `daytona`, `vercel`, `forkd`) cover most workflows; see [sandbox-providers.md](sandbox-providers.md) for the matrix. Reach for a custom provider when:

- You target a runtime Eden does not ship — gVisor, Kata, Nomad, Kubernetes Jobs, Modal, Fly Machines, Lambda, RunPod, or your own VM fleet. (Firecracker microVMs are covered in-tree by `forkd`, and E2B-compatible SDKs can reuse its approach.)
- You need a transport Eden does not ship — gRPC, SSH, WebSocket, etc.
- You want to wrap an existing in-tree provider with extra behavior (telemetry, caching, custom mount semantics).

If your provider only adds bind-mount semantics to a different container runtime, copy `eden/sandboxes/podman/__init__.py` — it is a 30-line file that delegates to `make_container_provider`.

## Protocol surface

Moved to [Custom provider protocols](custom-provider-protocols.md#protocol-surface).

Compatibility anchors: <a id="sandboxprovider"></a><a id="sandboxhandle"></a><a id="bindmountsandboxhandle"></a><a id="isolatedsandboxhandle"></a><a id="supporting-types"></a><a id="createoptions"></a><a id="execresult"></a><a id="finalizeresult"></a><a id="mount-branchstrategy"></a><a id="factory-helpers"></a><a id="make_bind_mount_provider"></a><a id="make_isolated_provider"></a>

- [`SandboxProvider`](custom-provider-protocols.md#sandboxprovider)
- [`SandboxHandle`](custom-provider-protocols.md#sandboxhandle)
- [`BindMountSandboxHandle`](custom-provider-protocols.md#bindmountsandboxhandle)
- [`IsolatedSandboxHandle`](custom-provider-protocols.md#isolatedsandboxhandle)
- [`CreateOptions`](custom-provider-reference.md#createoptions)
- [`ExecResult`](custom-provider-reference.md#execresult)
- [`FinalizeResult`](custom-provider-reference.md#finalizeresult)
- [`Mount`, `BranchStrategy`](custom-provider-reference.md#mount-branchstrategy)
- [`make_bind_mount_provider`](custom-provider-reference.md#make_bind_mount_provider)
- [`make_isolated_provider`](custom-provider-reference.md#make_isolated_provider)

## Skeleton: a custom isolated provider

Moved to [Custom provider skeleton](custom-provider-skeleton.md).

Compatibility anchors:

<a id="worked-examples-in-tree"></a>
<a id="conventions-worth-following"></a>

- [Worked examples in-tree](custom-provider-guide.md#worked-examples-in-tree)
- [Conventions worth following](custom-provider-guide.md#conventions-worth-following)

## See also

- [Python API: `IsolatedSandboxHandle`](python-api.md#isolatedsandboxhandle) — public re-export consumers can import from the top-level package.
- [Custom provider protocols](custom-provider-protocols.md) — Protocol reference.
- [Custom provider reference](custom-provider-reference.md) — supporting types and factory helpers.
- [Custom provider skeleton](custom-provider-skeleton.md) — minimum viable isolated provider.
- [Custom provider guide](custom-provider-guide.md) — in-tree examples and provider conventions.
- [Sandbox providers](sandbox-providers.md) — the in-tree provider catalog and matrix.
- [How it works](how-it-works.md) — where `create()`, `exec()`, and `finalize()` plug into the iteration loop.
- [Errors](errors.md) — `SandboxError` family raised by providers (`ProviderUnavailable`, `ExecFailed`, `ExecTimeout`, `UnsupportedStrategy`).
- [ADR 0001 — Finalizing vs. direct handles](adr/0001-finalizing-vs-direct-handles.md) — why `finalize()` is a per-iteration call rather than a streaming sync.
