# Python API: Cancellation

Detailed reference for cooperative cancellation and process shutdown callbacks.
See [Python API: Lifecycle](python-api-lifecycle.md) for lifecycle hooks.

## Cancellation

Cooperative cancellation uses an `AbortController` / `AbortSignal` pair. Pass
the signal to `run(signal=...)`, `interactive(signal=...)`,
`Sandbox.run(signal=...)`, or `WorktreeHandle.interactive(signal=...)`; call
`controller.abort()` from another thread to stop.

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

Reader side. Pollable via `is_aborted()`, blocking via `wait(timeout)`, and
assertable via `raise_if_aborted()` (raises `Aborted`).

### `Aborted`

```python
class Aborted(EdenError):
    def __init__(self, *, reason: str = "abort-signal") -> None: ...
```

Raised by `raise_if_aborted()` and surfaced from `run()` when cancellation
lands.

### `register_shutdown(callback)`

```python
def register_shutdown(callback: ShutdownCallback) -> Callable[[], None]: ...
```

Register a synchronous teardown that runs on `SIGINT`, `SIGTERM`, or normal
process exit. Returns an idempotent unregister function. The first registration
installs a single process-wide handler per signal; the last unregistration
removes it.

Use this when you create resources that need to be released even when the parent
process is killed without running `try/finally` (most notably `SIGTERM`).
`eden.run()` already wires its own teardown for the sandbox handle and worktree
it creates; `register_shutdown` is for caller-managed cleanup such as a cloud
workspace allocated outside `eden.run()`.

`callback` must be synchronous and tolerate running in a signal context.
Exceptions raised from one callback are swallowed; the rest still run.

### `ShutdownCallback`

```python
ShutdownCallback = Callable[[], None]
```

Type alias for `register_shutdown` callbacks.
