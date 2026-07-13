# Python API: Extensibility

Detailed reference for provider protocols. See [Python API: Lifecycle](python-api-lifecycle.md) for hooks and cancellation, [Python API: Display](python-api-display.md) for display sinks, and [Python API: Errors and tracing](python-api-errors-tracing.md) for error formatting, tracing, and version metadata.

---

## Lifecycle and cancellation

Moved to [Python API: Lifecycle](python-api-lifecycle.md).

Compatibility anchors: <a id="lifecycle-hooks"></a><a id="hook"></a><a id="hookphase"></a><a id="hosthooks"></a><a id="sandboxhooks"></a><a id="hooks"></a><a id="cancellation"></a><a id="abortcontroller"></a><a id="abortsignal"></a><a id="aborted"></a><a id="register_shutdowncallback"></a><a id="shutdowncallback"></a>

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

## <a id="display"></a><a id="displayentry"></a><a id="silentdisplay"></a><a id="filedisplay"></a><a id="richdisplay"></a>Display

Moved to [Python API: Display](python-api-display.md#display).

## Compatibility anchors

- <a id="errors"></a><a id="format_error_messageerror"></a>[Errors and formatting](python-api-errors-tracing.md#errors)
- <a id="tracing"></a>[Tracing](python-api-errors-tracing.md#tracing)
- <a id="version"></a><a id="__version__"></a>[Version](python-api-errors-tracing.md#version)
