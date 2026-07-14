# Custom provider guide

Implementation notes for out-of-tree sandbox providers. Start with
[Custom providers](custom-providers.md) for the Protocol reference and
[Custom provider skeleton](custom-provider-skeleton.md) for a minimal
implementation.

---

## Worked examples in-tree

Read these for full implementations of each shape:

- **Bind-mount, host-side** — `eden/sandboxes/no_sandbox/__init__.py`. ~60 LoC.
- **Bind-mount, container** — `eden/sandboxes/docker/__init__.py` and `eden/providers/_impl/container.py`. Delegates to a shared container helper.
- **Patch-sync, local** — `eden/sandboxes/isolated/__init__.py`. Copy-tree, snapshot, run, diff, apply.
- **REST cloud, isolated** — `eden/sandboxes/daytona/__init__.py`. Provisions a remote sandbox over REST, snapshots via `find -exec sha256sum`, pulls changed files in `finalize()`, and reuses `eden.providers._impl.patch_sync` for the apply step.
- **Test providers** — `eden/sandboxes/test_bind_mount/__init__.py` and `eden/sandboxes/test_isolated/__init__.py`. Filesystem-only providers that carve a tmpdir per `create()` call. Both expose a `CallLog` so tests can assert on the orchestrator's traffic, and accept an `exec_handler` callable to stub responses without spawning real subprocesses. Use them as a copy-paste starting point for your own provider.

```python
from eden import run, simulated_agent
from eden.sandboxes.test_bind_mount import CallLog, provider as test_bind_mount

log = CallLog()
result = run(
    sandbox=test_bind_mount(call_log=log),
    agent=simulated_agent(output="<promise>COMPLETE</promise>\n"),
    prompt="ignored",
    max_iterations=1,
)
assert log.closed is True
```

## Conventions worth following

- **Idempotent close** — `close()` is called from a `finally` block. Catch transport exceptions; never raise from `close()`.
- **Lazy credential checks** — raise `ProviderUnavailable` from `create()`, not from your `provider(...)` factory. This lets users import the factory without credentials in scope (matches `daytona`, `vercel`).
- **No `.git` / `.eden` upload** — the in-tree providers exclude these paths from the snapshot; do the same to keep finalize diffs small and avoid leaking session state into the sandbox.
- **Reuse `patch_sync`** — `eden.providers._impl.patch_sync` exposes `snapshot()`, `diff()`, and `apply()` so isolated providers do not have to reimplement the diff logic. `daytona` and `isolated` both use it.

## See also

- [Custom providers](custom-providers.md) — Protocol reference and factory helper signatures.
- [Custom provider skeleton](custom-provider-skeleton.md) — minimum viable isolated provider.
- [Sandbox providers](sandbox-providers.md) — the in-tree provider catalog and matrix.
- [Errors](errors.md) — provider error hierarchy and failure handling.
