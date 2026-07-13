# Custom providers

Implement the `SandboxProvider` Protocol — and one of `BindMountSandboxHandle` or `IsolatedSandboxHandle` for the handle it produces — to plug your own sandbox into `eden.run(sandbox=...)`.

## When to write one

The seven in-tree providers (`no_sandbox`, `docker`, `podman`, `isolated`, `daytona`, `vercel`, `forkd`) cover most workflows; see [sandbox-providers.md](sandbox-providers.md) for the matrix. Reach for a custom provider when:

- You target a runtime Eden does not ship — gVisor, Kata, Nomad, Kubernetes Jobs, Modal, Fly Machines, Lambda, RunPod, or your own VM fleet. (Firecracker microVMs are covered in-tree by `forkd`, and E2B-compatible SDKs can reuse its approach.)
- You need a transport Eden does not ship — gRPC, SSH, WebSocket, etc.
- You want to wrap an existing in-tree provider with extra behavior (telemetry, caching, custom mount semantics).

If your provider only adds bind-mount semantics to a different container runtime, copy `eden/sandboxes/podman/__init__.py` — it is a 30-line file that delegates to `make_container_provider`.

## Protocol surface

Eden defines four Protocols in `eden/providers/_protocols.py`. Three are runtime-checkable; the fourth (`SandboxProvider`) is the factory contract.

```mermaid
classDiagram
    class SandboxProvider {
        <<Protocol>>
        +name: str
        +kind: bind_mount|isolated|none
        +supports_strategy(strategy) bool
        +create(opts) SandboxHandle
    }
    class SandboxHandle {
        <<Protocol>>
        +worktree_path: Path
        +exec(cmd, on_line, ...) ExecResult
        +copy_file_in(src, dst)
        +copy_file_out(src, dst)
        +close()
    }
    class BindMountSandboxHandle {
        <<Protocol>>
    }
    class IsolatedSandboxHandle {
        <<Protocol>>
        +finalize(target) FinalizeResult
    }

    SandboxHandle <|-- BindMountSandboxHandle
    SandboxHandle <|-- IsolatedSandboxHandle
    SandboxProvider ..> SandboxHandle : create&#40;&#41; returns
```

### `SandboxProvider`

The factory side. Your `provider(...)` factory must return an instance satisfying this Protocol — use [`make_bind_mount_provider`](#make_bind_mount_provider) or [`make_isolated_provider`](#make_isolated_provider) instead of writing a bespoke class unless you have a reason.

All four Protocols, both factories, and every supporting type are re-exported from the top-level `eden` package, so out-of-tree providers can import them without depending on `eden.providers._protocols` directly:

```python
from eden import (
    BindMountSandboxHandle,
    BranchStrategy,
    CreateOptions,
    ExecResult,
    FinalizeResult,
    IsolatedSandboxHandle,
    Mount,
    SandboxHandle,
    SandboxProvider,
    make_bind_mount_provider,
    make_isolated_provider,
)
```

`kind` controls the orchestrator's behavior:

- `"bind_mount"` — host filesystem is mounted into the sandbox; no `finalize()` step.
- `"isolated"` — sandbox is detached; orchestrator calls `handle.finalize(target)` after each iteration.
- `"none"` — degenerate "sandbox" that just runs on the host (`no_sandbox`).

### `SandboxHandle`

The base handle Protocol every provider's `create()` must return. Runtime-checkable.

```python
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Protocol, runtime_checkable

from eden import ExecResult

@runtime_checkable
class SandboxHandle(Protocol):
    worktree_path: Path

    def exec(
        self,
        cmd: str,
        *,
        on_line: Callable[[str], None] | None = None,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
        stdin: str | None = None,
    ) -> ExecResult: ...

    def copy_file_in(self, host: Path, sandbox: Path) -> None: ...

    def copy_file_out(self, sandbox: Path, host: Path) -> None: ...

    def close(self) -> None: ...
```

- `worktree_path` — sandbox-side path the orchestrator passes to the agent as `cwd`. For bind-mount providers this is the host worktree; for isolated providers it is a sandbox-local path (e.g. `/workspace`).
- `exec(cmd, *, on_line, cwd, env, timeout, stdin)` — run a shell command. `cmd` is a string (not argv); the provider chooses how to evaluate it (`/bin/sh -c`, REST shell, etc.). `on_line` is invoked once per stdout line as the command runs (use it to forward to the orchestrator's streaming layer). `stdin`, when given, is written to the command's stdin so the caller can deliver payloads larger than the 128KB Linux execve argv limit; bind-mount providers pipe directly, REST providers (daytona, vercel) wrap the command with `printf <base64> | base64 -d | (cmd)`.
- `copy_file_in` / `copy_file_out` — single-file transfers between host and sandbox. Used by hooks and session capture.
- `close()` — release resources. Called in a `finally` block; should not raise.

### `BindMountSandboxHandle`

A marker Protocol — adds no methods over `SandboxHandle`. Lets the orchestrator narrow types when it knows a handle is bind-mount.

```python
@runtime_checkable
class BindMountSandboxHandle(SandboxHandle, Protocol):
    """Marker — bind-mount providers don't add methods."""
```

### `IsolatedSandboxHandle`

The handle Protocol for detached / patch-sync / cloud sandboxes. Adds one method.

```python
from eden import FinalizeResult

@runtime_checkable
class IsolatedSandboxHandle(SandboxHandle, Protocol):
    def finalize(self, target: Path) -> FinalizeResult: ...
```

`finalize(target)` replays the sandbox-side state onto the host worktree (`target`). The orchestrator detects the Protocol via `hasattr(handle, "finalize")`, so any handle exposing the method works — the runtime-checkable Protocol is for type-checker narrowing.

`IsolatedSandboxHandle` is re-exported from the top-level `eden` package, so out-of-tree providers can `from eden import IsolatedSandboxHandle` without depending on `eden.providers._protocols` directly. See [python-api.md#isolatedsandboxhandle](python-api.md#isolatedsandboxhandle).

## Supporting types

Read these from `eden/providers/_types.py`. All are frozen dataclasses.

### `CreateOptions`

The single argument the orchestrator hands to your `create()` callable.

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

- `branch` — the worktree's branch name.
- `worktree_path` — host path the orchestrator carved.
- `host_repo_path` — root of the user's repo (parent of `.eden/`).
- `env` — environment variables to forward into the sandbox.
- `mounts` — extra bind mounts the caller requested via the provider factory.
- `name_hint` — `run(name=...)` value, useful for cloud sandbox names.

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

`check()` raises [`ExecFailed`](errors.md) if `exit_code != 0`. Returned by every `handle.exec(...)` call.

### `FinalizeResult`

```python
@dataclass(frozen=True)
class FinalizeResult:
    applied: bool
    files_changed: tuple[Path, ...]
    patch_size_bytes: int
```

What `IsolatedSandboxHandle.finalize(target)` returns. `applied=False` means at least one copy or unlink failed; failures are logged and the orchestrator continues.

### `Mount`, `BranchStrategy`

See [python-api.md#configuration-types](python-api.md#configuration-types) for the public dataclasses. Your factory accepts `mounts: tuple[Mount, ...]` from the caller and threads them through to `CreateOptions`.

## Factory helpers

Eden ships two factories that wrap a `create` callable into a `SandboxProvider` so you do not have to write the boilerplate yourself. Both are re-exported from the top-level `eden` package.

### `make_bind_mount_provider`

```python
from collections.abc import Callable
from eden import (
    BindMountSandboxHandle,
    CreateOptions,
    SandboxProvider,
    make_bind_mount_provider,
)
from eden.providers import StrategyTag

def make_bind_mount_provider(
    name: str,
    create: Callable[[CreateOptions], BindMountSandboxHandle],
    *,
    supported_strategies: frozenset[StrategyTag] = frozenset(
        {"head", "merge_to_head", "named"}
    ),
) -> SandboxProvider: ...
```

Use for any provider where the host worktree is the sandbox (host == sandbox filesystem). The orchestrator will not call `finalize()` on the returned handle.

### `make_isolated_provider`

```python
from eden import IsolatedSandboxHandle, SandboxProvider, make_isolated_provider

def make_isolated_provider(
    name: str,
    create: Callable[[CreateOptions], IsolatedSandboxHandle],
    *,
    supported_strategies: frozenset[StrategyTag] = frozenset(
        {"head", "merge_to_head", "named"}
    ),
) -> SandboxProvider: ...
```

Use for detached, patch-sync, or cloud providers. The handle returned by `create` MUST expose `finalize(target) -> FinalizeResult`.

## Skeleton: a custom isolated provider

Moved to [Custom provider guide](custom-provider-guide.md#skeleton-a-custom-isolated-provider).

Compatibility anchors:

<a id="worked-examples-in-tree"></a>
<a id="conventions-worth-following"></a>

- [Worked examples in-tree](custom-provider-guide.md#worked-examples-in-tree)
- [Conventions worth following](custom-provider-guide.md#conventions-worth-following)

## See also

- [Python API: `IsolatedSandboxHandle`](python-api.md#isolatedsandboxhandle) — public re-export consumers can import from the top-level package.
- [Custom provider guide](custom-provider-guide.md) — skeleton implementation, in-tree examples, and provider conventions.
- [Sandbox providers](sandbox-providers.md) — the in-tree provider catalog and matrix.
- [How it works](how-it-works.md) — where `create()`, `exec()`, and `finalize()` plug into the iteration loop.
- [Errors](errors.md) — `SandboxError` family raised by providers (`ProviderUnavailable`, `ExecFailed`, `ExecTimeout`, `UnsupportedStrategy`).
- [ADR 0001 — Finalizing vs. direct handles](adr/0001-finalizing-vs-direct-handles.md) — why `finalize()` is a per-iteration call rather than a streaming sync.
