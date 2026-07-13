# Custom provider reference

Supporting dataclasses and factory helpers for out-of-tree sandbox providers.
See [Custom provider protocols](custom-provider-protocols.md) for the
`SandboxProvider` and handle Protocol surface.

## Supporting types

Supporting types live in `eden/providers/_types.py`; all are frozen dataclasses.

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

- `branch` - the worktree's branch name.
- `worktree_path` - host path the orchestrator carved.
- `host_repo_path` - root of the user's repo (parent of `.eden/`).
- `env` - environment variables to forward into the sandbox.
- `mounts` - extra bind mounts the caller requested via the provider factory.
- `name_hint` - `run(name=...)` value, useful for cloud sandbox names.

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

`check()` raises [`ExecFailed`](errors.md) if `exit_code != 0`. Returned by
every `handle.exec(...)` call.

### `FinalizeResult`

```python
@dataclass(frozen=True)
class FinalizeResult:
    applied: bool
    files_changed: tuple[Path, ...]
    patch_size_bytes: int
```

What `IsolatedSandboxHandle.finalize(target)` returns. `applied=False` means at
least one copy or unlink failed; failures are logged and the orchestrator
continues.

### `Mount`, `BranchStrategy`

See [python-api-types.md#configuration-types](python-api-types.md#configuration-types).
Your factory accepts `mounts: tuple[Mount, ...]` from the caller and threads
them through to `CreateOptions`.

## Factory helpers

Eden ships two top-level factories that wrap a `create` callable into a
`SandboxProvider`.

### `make_bind_mount_provider`

```python
provider = make_bind_mount_provider(name="my-provider", create=my_create_fn)
```

Use for any provider where the host worktree is the sandbox, so host and
sandbox filesystems are the same. The orchestrator will not call `finalize()` on
the returned handle. Pass `supported_strategies=` to restrict the default set
(`head`, `merge_to_head`, `named`).

### `make_isolated_provider`

```python
provider = make_isolated_provider(name="my-provider", create=my_create_fn)
```

Use for detached, patch-sync, or cloud providers. The handle returned by
`create` must expose `finalize(target) -> FinalizeResult`.
