# Python API: Lifecycle

Detailed reference for lifecycle hooks and cooperative cancellation. See
[Python API: Extensibility](python-api-extensibility.md) for provider Protocols.

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

Cooperative cancellation uses an `AbortController` / `AbortSignal` pair. Pass the signal to `run(signal=...)`, `interactive(signal=...)`, `Sandbox.run(signal=...)`, or `WorktreeHandle.interactive(signal=...)`; call `controller.abort()` from another thread to stop.

### `AbortController`

```python
@dataclass
class AbortController:
    signal: AbortSignal = field(default_factory=AbortSignal)

    def abort(self, *, reason: str = "abort-signal") -> None: ...
```

Writer side. `abort()` is idempotent: only the first call records a `reason`.

### `AbortSignal`

```python
@dataclass
class AbortSignal:
    def is_aborted(self) -> bool: ...
    @property
    def reason(self) -> str | None: ...
    def raise_if_aborted(self) -> None: ...
    def wait(self, timeout: float | None = None) -> bool: ...
```

Reader side. Pollable via `is_aborted()`, blocking via `wait(timeout)`, and assertable via `raise_if_aborted()` (raises `Aborted`).

### `Aborted`

```python
class Aborted(EdenError):
    def __init__(self, *, reason: str = "abort-signal") -> None: ...
```

Raised by `raise_if_aborted()` and surfaced from `run()` when cancellation lands.

### `register_shutdown(callback)`

```python
def register_shutdown(callback: ShutdownCallback) -> Callable[[], None]: ...
```

Register a synchronous teardown that runs on `SIGINT`, `SIGTERM`, or normal process exit. Returns an idempotent unregister function. The first registration installs a single process-wide handler per signal; the last unregistration removes it.

Use this when you create resources that need to be released even when the parent process is killed without running `try/finally` (most notably `SIGTERM`). `eden.run()` already wires its own teardown for the sandbox handle and worktree it creates; `register_shutdown` is for caller-managed cleanup such as a cloud workspace allocated outside `eden.run()`.

`callback` must be synchronous and tolerate running in a signal context. Exceptions raised from one callback are swallowed; the rest still run.

### `ShutdownCallback`

```python
ShutdownCallback = Callable[[], None]
```

Type alias for `register_shutdown` callbacks.
