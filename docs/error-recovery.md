# Error Recovery

Handling strategies and catch-all examples for Eden errors. See [Errors](errors.md) for the full hierarchy and class reference.

---

## Recovery patterns at a glance

| Error | Strategy |
|---|---|
| `ConfigError` (any subclass) | Fix the call site / config; re-run. |
| `HookFailed` / `HookTimeout` | Fix the hook command or raise the timeout. |
| `IdleTimeout` / `StepTimeout` | Raise `idle_timeout` / `Timeouts.iteration_step`, or investigate the agent. |
| `Aborted` | Intentional cancellation; treat as success. |
| `SessionCaptureFailed` | Already non-fatal; ignored unless you opt into stricter handling. |
| `RestRateLimited` | Retry with backoff. |
| `RestAuthError` | Rotate credentials. |
| `RestNotFoundError` | Resource is gone; do not retry the same ID. |
| `RestError` (other) | Inspect `e.status` / `e.body`; usually transient. |
| `ProviderUnavailable` | Install the missing binary / set the missing env var. |
| `ImageNotFound` | Build or pull the image. |
| `ContainerStartFailed` | Inspect `e.stderr`; fix the image. |
| `ExecFailed` / `ExecTimeout` | Inspect `e.result.stderr`; fix the command or raise the timeout. |
| `MountConfigError` | Mount the parent directory or pre-create the target parent in the image. |
| `UnsupportedStrategy` | Pick a supported `BranchStrategy` or switch providers. |
| `WorktreeLocked` | Wait, kill the holder, or change branch. |
| `DirtyHostBlocked` | Commit / stash / discard, or switch branch strategy. |
| `BranchExists` | Pick a different branch name. |
| `GitCommandFailed` | Read `e.stderr`; fix the repo. |

## Catching everything

```python
from eden import EdenError, run

try:
    result = run(...)
except EdenError as e:
    code = getattr(e, "code", None)  # not every error carries a code
    log.error("eden failure (code=%s): %s", code, e)
    raise
```

For structured logging, every error in `eden/errors.py` (top-level group, except `Aborted` and `EdenError`/`HookError`/`EdenTimeoutError`/`RestError` bases) exposes `code`, `message`, and `hint` attributes — read them directly. The `SandboxError` and `WorktreeError` families instead expose typed fields specific to the failure (e.g. `e.image`, `e.holder_pid`).

## See also

- [Errors](errors.md) — the class hierarchy and taxonomy.
- [Sandbox and worktree errors](sandbox-worktree-errors.md) — provider and worktree error details.
- [How it works](how-it-works.md) — where errors surface in the iteration loop.
