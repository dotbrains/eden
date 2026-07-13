# Python API: Extensibility

Detailed reference for lifecycle hooks, cancellation, provider protocols, and display sinks. See [Python API](python-api.md) for the canonical public API index, and [Python API: Errors and tracing](python-api-errors-tracing.md) for error formatting, tracing, and version metadata.

---

## Lifecycle hooks

Eden runs commands at five named phases — `HookPhase` enumerates them and `Hooks` bundles host-side and sandbox-side variants.

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

Order: `OnWorktreeReady` (host) → `OnSandboxReady` (sandbox) → for each iteration `OnIterationStart` → agent → `OnIterationEnd` → on exit `OnClose`.

### `HostHooks`

```python
@dataclass(frozen=True)
class HostHooks:
    on_worktree_ready: tuple[Hook, ...] = ()
    on_iteration_start: tuple[Hook, ...] = ()
    on_iteration_end: tuple[Hook, ...] = ()
    on_close: tuple[Hook, ...] = ()
```

Host hooks run sequentially on the workstation. Note: `on_sandbox_ready` is sandbox-only.

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

---

## Cancellation

Cooperative cancellation uses an `AbortController` / `AbortSignal` pair. Pass the signal to `run(signal=...)`, `interactive(signal=...)`, `Sandbox.run(signal=...)`, or `WorktreeHandle.interactive(signal=...)`; call `controller.abort()` from another thread to stop.

### `AbortController`

```python
@dataclass
class AbortController:
    signal: AbortSignal = field(default_factory=AbortSignal)

    def abort(self, *, reason: str = "abort-signal") -> None: ...
```

Writer side. `abort()` is idempotent — only the first call records a `reason`.

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

Use this when you create resources that need to be released even when the parent process is killed without running `try/finally` (most notably `SIGTERM`). `eden.run()` already wires its own teardown for the sandbox handle and worktree it creates — `register_shutdown` is for caller-managed cleanup (e.g. a cloud workspace allocated outside `eden.run()`).

`callback` must be synchronous and tolerate running in a signal context. Exceptions raised from one callback are swallowed; the rest still run.

### `ShutdownCallback`

```python
ShutdownCallback = Callable[[], None]
```

Type alias for `register_shutdown` callbacks.

---

## Provider Protocol re-exports

Eden re-exports the full provider surface from the top-level package so consumers can build cloud or out-of-tree providers without depending on `eden.providers._protocols` directly. See [custom-providers.md](custom-providers.md) for the full walk-through.

### `SandboxHandle`

```python
@runtime_checkable
class SandboxHandle(Protocol):
    worktree_path: Path
    def exec(self, cmd: str, *, on_line, cwd, env, timeout, stdin) -> ExecResult: ...
    def copy_file_in(self, host: Path, sandbox: Path) -> None: ...
    def copy_file_out(self, sandbox: Path, host: Path) -> None: ...
    def close(self) -> None: ...
```

The base handle every provider's `create()` must return. Runtime-checkable. `exec(stdin=...)` writes the supplied string to the command's stdin so callers can deliver large payloads without hitting the 128KB execve argv cap (REST providers wrap with `printf <base64> | base64 -d | (cmd)`).

### `BindMountSandboxHandle`

Marker subprotocol of `SandboxHandle` — no extra methods. Used by `docker`, `podman`, `no_sandbox` and any custom provider that runs the agent against a host-mounted worktree.

### `IsolatedSandboxHandle`

```python
@runtime_checkable
class IsolatedSandboxHandle(SandboxHandle, Protocol):
    def finalize(self, target: Path) -> FinalizeResult: ...
```

A `SandboxHandle` whose state replicates back to the host on close via `finalize(target)`. The orchestrator detects the protocol via `hasattr(handle, "finalize")`. Bind-mount providers (docker, podman, no_sandbox) do not implement it.

### `SandboxProvider`

```python
@runtime_checkable
class SandboxProvider(Protocol):
    name: str
    kind: Literal["bind_mount", "isolated", "none"]
    def supports_strategy(self, strategy: BranchStrategy) -> bool: ...
    def create(self, opts: CreateOptions) -> SandboxHandle: ...
```

The factory contract. Wrap a `create` callable with [`make_bind_mount_provider`](#make_bind_mount_provider) or [`make_isolated_provider`](#make_isolated_provider) instead of implementing this class by hand unless you have a reason.

### `CreateOptions`

```python
@dataclass(frozen=True)
class CreateOptions:
    branch: str
    worktree_path: Path
    host_repo_path: Path
    env: Mapping[str, str]
    mounts: tuple[Mount, ...]
    name_hint: str | None
```

The argument the orchestrator hands to your `create()` callable.

### `ExecResult`

```python
@dataclass(frozen=True)
class ExecResult:
    stdout: str
    stderr: str
    exit_code: int

    @property
    def ok(self) -> bool: ...
    def check(self) -> ExecResult: ...
```

Returned by `handle.exec(...)`. `check()` raises [`ExecFailed`](errors.md) if `exit_code != 0`.

### `make_bind_mount_provider`

```python
from eden import make_bind_mount_provider

provider = make_bind_mount_provider(name="my-provider", create=my_create_fn)
```

Wraps a `create: Callable[[CreateOptions], BindMountSandboxHandle]` into a `SandboxProvider` with `kind="bind_mount"`. Accepts an optional `supported_strategies: frozenset[StrategyTag]` to restrict the branch strategies your provider supports (default: all three).

### `make_isolated_provider`

```python
from eden import make_isolated_provider

provider = make_isolated_provider(name="my-provider", create=my_create_fn)
```

Same idea, but the returned handle must expose `finalize(target) -> FinalizeResult`. Produces a provider with `kind="isolated"`.

---

## Display

A swappable sink abstraction for orchestrator → user output. Eden re-exports the Protocol and three concrete sinks; pass any of them to higher-level CLI / interactive helpers that accept a `display=` argument. Built on a tagged `DisplayEntry` ADT.

### `Display`

```python
class Display(Protocol):
    def intro(self, title: str) -> None: ...
    def status(self, message: str, severity: Severity = "info") -> None: ...
    def text(self, message: str) -> None: ...
    def text_chunk(self, chunk: str) -> None: ...
    def tool_call(self, name: str, formatted_args: str) -> None: ...
    def summary(self, title: str, rows: Mapping[str, str]) -> None: ...
    @contextmanager
    def spinner(self, message: str) -> Iterator[None]: ...
    @contextmanager
    def task_log(self, title: str) -> Iterator[Callable[[str], None]]: ...
```

`Severity` is one of `"info" | "success" | "warn" | "error"`. `text()` emits a line-oriented message; `text_chunk()` emits raw streaming text with no implied newline, so adjacent chunks render as contiguous prose. The two context managers wrap long-running blocks: `spinner` for an indeterminate progress indicator; `task_log` for collecting per-step messages and emitting them on exit (the yielded callable pushes messages into the log).

### `DisplayEntry`

Tagged-union of `IntroEntry | StatusEntry | SpinnerEntry | SummaryEntry | TaskLogEntry | TextEntry | TextChunkEntry | ToolCallEntry`. Each has a `.tag` literal and the relevant payload fields. Used by `SilentDisplay` to record everything for test assertions.

### `SilentDisplay`

```python
display = SilentDisplay()
# ... orchestrator runs ...
assert display.entries[-1].title == "Run complete"
```

Records every entry on `.entries`, prints nothing. The test sink.

### `FileDisplay`

```python
display = FileDisplay(Path(".eden/logs/run.log"))
```

Append-only file sink with timestamped delimiter on construction. Spinners and task logs record their duration. `text_chunk()` writes chunks verbatim, and later line-oriented entries start on a fresh line if a chunk ended mid-line. Suitable for unattended / CI runs.

### `RichDisplay`

```python
display = RichDisplay()  # uses default rich.console.Console()
```

Live terminal output powered by the bundled `rich` dependency. Renders severities with color glyphs, spinners with `rich.status.Status`, summaries as bold-key / dim-value blocks. Inject a custom `Console` via `RichDisplay(console=Console(file=...))` for capturing tests.

---

## Errors

Moved to [Python API: Errors and tracing](python-api-errors-tracing.md#errors).

### `format_error_message(error)`

Moved to [Python API: Errors and tracing](python-api-errors-tracing.md#format_error_messageerror).

---

## Tracing

Moved to [Python API: Errors and tracing](python-api-errors-tracing.md#tracing).

---

## Version

### `__version__`

Moved to [Python API: Errors and tracing](python-api-errors-tracing.md#__version__).
