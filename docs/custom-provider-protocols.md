# Custom provider protocols

Detailed `SandboxProvider` and handle Protocol reference for out-of-tree sandbox
providers. See [Custom providers](custom-providers.md) for when to write one and
[Custom provider guide](custom-provider-guide.md) for a skeleton implementation.

## Protocol surface

Eden defines four Protocols in `eden/providers/_protocols.py`: `SandboxProvider`
creates a `SandboxHandle`; bind-mount and isolated handles specialize it.
Isolated handles add `finalize(target)`.

### `SandboxProvider`

The factory side. Your `provider(...)` factory must return this Protocol. Prefer
the [bind-mount](custom-provider-reference.md#make_bind_mount_provider) or
[isolated](custom-provider-reference.md#make_isolated_provider) factory helper
over a bespoke class.

All Protocols, factories, and supporting types are re-exported from `eden`.
Common imports include `SandboxProvider`, `SandboxHandle`,
`BindMountSandboxHandle`, `IsolatedSandboxHandle`, `CreateOptions`,
`ExecResult`, `FinalizeResult`, `Mount`, `BranchStrategy`, both factory helpers.

`kind` controls the orchestrator's behavior:

- `"bind_mount"` - host filesystem is mounted into the sandbox; no `finalize()`.
- `"isolated"` - sandbox is detached; orchestrator calls
  `handle.finalize(target)` after each iteration.
- `"none"` - degenerate "sandbox" that just runs on the host (`no_sandbox`).

### `SandboxHandle`

The runtime-checkable handle Protocol every provider's `create()` must return.

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

- `worktree_path` - sandbox-side path the orchestrator passes to the agent as
  `cwd`. For bind-mount providers this is the host worktree; for isolated
  providers it is a sandbox-local path (for example, `/workspace`).
- `exec(cmd, *, on_line, cwd, env, timeout, stdin)` - run a shell command. The
  provider chooses how to evaluate the string (`/bin/sh -c`, REST shell, etc.).
  `on_line` is invoked once per stdout line. `stdin` carries payloads larger
  than the 128KB Linux execve argv limit; REST providers wrap with
  `printf <base64> | base64 -d | (cmd)`.
- `copy_file_in` / `copy_file_out` - single-file transfers between host and
  sandbox. Used by hooks and session capture.
- `close()` - release resources. Called in a `finally` block; should not raise.

### `BindMountSandboxHandle`
A marker Protocol that adds no methods over `SandboxHandle`. It lets the
orchestrator narrow types when it knows a handle is bind-mount.

### `IsolatedSandboxHandle`

The handle Protocol for detached / patch-sync / cloud sandboxes.

```python
from eden import FinalizeResult

@runtime_checkable
class IsolatedSandboxHandle(SandboxHandle, Protocol):
    def finalize(self, target: Path) -> FinalizeResult: ...
```

`finalize(target)` replays sandbox-side state onto the host worktree (`target`).
The orchestrator detects the Protocol via `hasattr(handle, "finalize")`, so any
handle exposing the method works. The runtime-checkable Protocol is for
type-checker narrowing.

`IsolatedSandboxHandle` is re-exported from the top-level `eden` package, so
out-of-tree providers can `from eden import IsolatedSandboxHandle` without
depending on `eden.providers._protocols` directly. See
[python-api.md#isolatedsandboxhandle](python-api.md#isolatedsandboxhandle).

## Supporting types and factories

Moved to [Custom provider reference](custom-provider-reference.md).

Compatibility anchors:
<a id="supporting-types"></a><a id="createoptions"></a><a id="execresult"></a><a id="finalizeresult"></a><a id="mount-branchstrategy"></a><a id="factory-helpers"></a><a id="make_bind_mount_provider"></a><a id="make_isolated_provider"></a>
