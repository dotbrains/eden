# Python API: Lifecycle

Detailed reference for lifecycle hooks. See
[Python API: Cancellation](python-api-cancellation.md) for abort signals and
shutdown callbacks, and [Python API: Extensibility](python-api-extensibility.md)
for provider Protocols.

---

## Lifecycle hooks

Eden runs commands at five named phases: `HookPhase` enumerates them and `Hooks` bundles host-side and sandbox-side variants.

### `Hook`

```python
@dataclass(frozen=True)
class Hook:
    cmd: str
    cwd: Path | None = None
    env: Mapping[str, str] | None = None
    timeout: float | None = None
```

A single shell command to run. `timeout=None` defers to `Timeouts.hook_step`.

### `HookPhase`

```python
class HookPhase(Enum):
    OnWorktreeReady = "on_worktree_ready"
    OnSandboxReady = "on_sandbox_ready"
    OnIterationStart = "on_iteration_start"
    OnIterationEnd = "on_iteration_end"
    OnClose = "on_close"
```

Order: `OnWorktreeReady` (host) -> `OnSandboxReady` (sandbox) -> for each iteration `OnIterationStart` -> agent -> `OnIterationEnd` -> on exit `OnClose`.

### `HostHooks`

```python
@dataclass(frozen=True)
class HostHooks:
    on_worktree_ready: tuple[Hook, ...] = ()
    on_iteration_start: tuple[Hook, ...] = ()
    on_iteration_end: tuple[Hook, ...] = ()
    on_close: tuple[Hook, ...] = ()
```

Host hooks run sequentially on the workstation. `on_sandbox_ready` is sandbox-only.

### `SandboxHooks`

```python
@dataclass(frozen=True)
class SandboxHooks:
    on_sandbox_ready: tuple[Hook, ...] = ()
    on_iteration_start: tuple[Hook, ...] = ()
    on_iteration_end: tuple[Hook, ...] = ()
    on_close: tuple[Hook, ...] = ()
```

Sandbox hooks run inside the sandbox handle. They may execute in parallel where the provider supports it.

### `Hooks`

```python
@dataclass(frozen=True)
class Hooks:
    host: HostHooks = field(default_factory=HostHooks)
    sandbox: SandboxHooks = field(default_factory=SandboxHooks)
```

Failure mapping: a hook that exits non-zero raises `HookFailed`; exceeding its `timeout` raises `HookTimeout`. Both are subclasses of `HookError`.

## Cancellation

Moved to [Python API: Cancellation](python-api-cancellation.md#cancellation).
