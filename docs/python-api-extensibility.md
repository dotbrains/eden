# Python API: Extensibility, Errors, and Tracing

Detailed reference for lifecycle hooks, cancellation, provider protocols, display sinks, errors, tracing, and version metadata. See [Python API](python-api.md) for the canonical public API index.

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

Every error eden raises descends from `EdenError`. Each concrete class accepts a `cause` keyword argument and carries `code`, `message`, and `hint` attributes for structured logging. `EdenTimeoutError` additionally subclasses the built-in `TimeoutError` for mixed-`except` ergonomics. See [errors.md](errors.md) for the full taxonomy with `code` strings, raise sites, and recovery guidance.

### `format_error_message(error)`

```python
from eden import EdenError, format_error_message, run

try:
    run(agent=..., sandbox=..., prompt="...")
except EdenError as e:
    print(format_error_message(e))
```

Maps any `EdenError` (including the sandbox / worktree subclasses) to a single multi-line user-friendly string of the form:

    <kind-prefix>: <message>
      code: <code>
      hint: <hint>

`hint` is preserved when the error already carries one (e.g. `InvalidOptions(..., hint=...)`). For tagged provider errors that don't carry a hint — `ProviderUnavailable`, `ImageNotFound`, `ContainerStartFailed`, `ExecTimeout`, etc. — the formatter synthesises a context-aware suggestion ("Is Docker running?", "Build the image first: `docker build ...`", "Increase `Timeouts.iteration_step`"). Use this in CLI surfaces so users get the same recovery message regardless of which error subclass surfaced.

The 20 concrete error classes re-exported from `eden`:

- `EdenError` — base class for everything.
- `AgentError` — the agent subprocess exited non-zero without hitting the completion signal. Carries `agent_name`, `exit_code`, `stderr`, and `parsed_error` (extracted from stdout for Codex / Pi / OpenCode, which surface errors there rather than on stderr).
- `ConfigError` — bad arguments, env, or cwd; raised before any side-effect.
- `CopyToWorktreeError` — a worktree copy failed. Raised in two places: (1) the isolated provider's worktree clone failed or exceeded `Timeouts.copy_to_worktree`; (2) a `copy_to_worktree=` entry passed to `run()` / `create_sandbox()` / `interactive()` doesn't exist on disk, or the copy hit a permissions / disk-space error. Carries `source`, `target`, `timeout`, and `timed_out` (true on budget overrun, false on missing-source / permission / disk failure).
- `CwdError` — invalid `cwd=` (missing, not a directory, not in a git repo).
- `EdenTimeoutError` — base for time-budget exceedances; subclasses `TimeoutError`.
- `EnvMergeError` — conflicting `env` overrides between caller, agent, and provider.
- `FloxEnvError` — an agent declared a `flox_env` that can't be activated: the directory has no `.flox/env/manifest.toml`, or the `flox` binary isn't on `PATH`. Raised before the first iteration (fail-fast). Set `EDEN_ALLOW_NO_FLOX=1` to skip activation when `flox` is unavailable. Code `config.flox_env`.
- `HookError` — base for hook failures.
- `HookFailed` — a hook command exited non-zero.
- `HookTimeout` — a hook exceeded `Timeouts.hook_step` (or its own `timeout`).
- `IdleTimeout` — agent stdout was silent past `idle_timeout` before any completion signal was seen. After a completion signal, `completion_timeout` bounds the success-path drain instead.
- `InvalidOptions` — generic kwarg validation failure.
- `PromptError` — `prompt`/`prompt_file`/`prompt_args` resolution failed.
- `RestAuthError` — 401/403 from a cloud provider's REST API.
- `RestError` — base for any non-2xx REST response (or `status=0` connection failure).
- `RestNotFoundError` — 404 from a cloud provider.
- `RestRateLimited` — 429 after retries were exhausted.
- `SessionCaptureFailed` — the orchestrator could not locate or read a session JSONL; soft failure surfaced as a warning event.
- `SessionNotFound` — raised at run start when `resume_session=<id>` references a JSONL that does not exist on the host filesystem. The orchestrator runs this precheck before spawning the agent so the failure surfaces host-side with the expected path, rather than buried in agent stderr. Carries `session_id`, `agent_name`, optional `expected_path`, and `hint`.
- `StepTimeout` — an iteration exceeded `Timeouts.iteration_step`.
- <a id="structuredoutputerror"></a>`StructuredOutputError` — `output=Output.{object,string}(...)` failed to extract or validate. Carries `tag`, `raw_matched` (the matched contents or `None`), `branch`, optional `preserved_worktree_path`, and — when the failing iteration was captured — `session_id` and `session_file_path` so claude_code callers can resume that conversation with corrective feedback via `resume_session=`. Raised on missing tag, invalid JSON, or schema validation failure.

---

## Tracing

Eden emits OpenTelemetry spans for the iteration loop, sandbox lifecycle, hooks, and REST requests. The runtime depends on `opentelemetry-api>=1.20`; without an installed SDK, OTel's no-op tracer makes every span a zero-cost noop. To collect traces in your application, install `opentelemetry-sdk` and configure a provider/exporter — eden picks up whatever provider is set globally.

Spans emitted:

| Span | Where | Key attributes |
| --- | --- | --- |
| `eden.run` | one per `eden.run()` / `eden.aio.run()` call | `agent.name`, `agent.model`, `sandbox.name`, `sandbox.kind`, `branch`, `max_iterations`, `caller_managed`, `iterations`, `completion_signal` |
| `eden.sandbox.create` | wraps `Sandbox.create` + `OnSandboxReady` hooks | `sandbox.name`, `sandbox.kind`, `branch` |
| `eden.agent.exec` | one per agent invocation (per iteration) | `agent.name`, `agent.model`, `iteration.index`, `branch` |
| `eden.hook` | one per host or sandbox hook command | `hook.location` (`host`/`sandbox`), `hook.phase`, `hook.command`, `hook.timeout_s` |
| `eden.rest.request` | one per `RestClient` HTTP request | `http.method`, `http.url`, `http.status_code`, `http.retry_count` |

All spans record exceptions via `Span.record_exception()` and set status to `ERROR` on raise — failures show up in your trace UI without extra wiring.

Every span also emits two metrics derived from its name:

- `<span>.count` — counter, attribute `outcome` ∈ `{ok, error}`.
- `<span>.duration_seconds` — histogram, same `outcome` attribute.

So `eden.run.count{outcome="error"}` gives you the failure rate across runs, and `eden.agent.exec.duration_seconds` (P50/P95) tells you whether iterations are getting slower over time. Wire up an OTel `MeterProvider` alongside the `TracerProvider` to receive them.

A minimal SDK setup for local debugging:

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor

provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(provider)

import eden
eden.run(agent=..., sandbox=..., prompt="...")
```

See [ADR 0012](adr/0012-otel-tracing.md) for the design rationale and instrumented site list.

---

## Version

### `__version__`

```python
import eden
print(eden.__version__)
```

`eden.__version__` exposes the installed package version (read via `importlib.metadata`). Unit tests assert the value matches `pyproject.toml`.
