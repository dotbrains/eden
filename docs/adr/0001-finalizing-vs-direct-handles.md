# ADR 0001 — Finalizing vs. direct handles

**Status:** Accepted (2026-05-02).

## Context

Sandbox providers fall into two shapes:

- **Bind-mount** — the worktree path is mounted into the sandbox; the agent reads and writes the host filesystem directly.
- **Detached** — the sandbox lives elsewhere (a separate directory, a remote VM). Files are copied in, the agent writes locally, then the diff has to come back.

For detached providers we needed a way to express "now sync your changes back to the host." Two options were considered:

1. **Streaming sync** — the sandbox handle exposes a file-watcher that mirrors writes back continuously.
2. **Post-iteration `finalize()`** — the handle exposes one method that, when called, returns a `FinalizeResult` containing a diff to apply.

## Decision

Adopt option 2. The Protocol is `IsolatedSandboxHandle.finalize(target) -> FinalizeResult`. Bind-mount handles do not implement `finalize`; their changes are already on disk.

## Consequences

- Sandbox-side code stays simple — providers don't need a write watcher.
- Iteration semantics match between bind-mount and detached: every iteration ends with the host worktree at a known state.
- Per-iteration sync works (the orchestrator calls `finalize()` after each iteration); no streaming partial-write states are observable.
- The downside: detached sandboxes pay a sync cost at each iteration boundary. For typical agent runs (seconds to minutes per iteration) this is negligible.

## See also

- [`docs/custom-providers.md`](../custom-providers.md) — the four Protocols and how to implement them.
- [`docs/sandbox-providers.md`](../sandbox-providers.md) — which shipped providers use which Protocol.
