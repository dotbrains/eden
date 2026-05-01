# Eden Phase 2 — Sandbox Foundations Design

**Status:** Approved 2026-05-01
**Phase:** 2 of 7 in the [Eden Python rewrite](2026-04-30-eden-python-rewrite-design.md)
**Effort estimate:** ~2 weeks
**Predecessor:** [Phase 1 — Skeleton & Packaging](2026-04-30-eden-phase1-skeleton.md)

## 1. Scope & deliverables

Phase 2 lands the runtime substrate that every later phase builds on: provider Protocols, the worktree manager, two concrete sandbox providers (`no_sandbox` and `docker` MVP), and a top-level `create_sandbox()` factory. The `eden run` orchestrator is **not** part of this phase — it ships in Phase 3.

### Public surface added in this phase

| Module | Exposes |
|---|---|
| `eden.providers` | `SandboxProvider`, `SandboxHandle`, `BindMountSandboxHandle`, `ExecResult`, `CreateOptions`, `Mount`, `BranchStrategy`, `StrategyTag`, `make_bind_mount_provider` |
| `eden.worktree` | `create_worktree`, `WorktreeHandle`, `CloseResult` |
| `eden.sandboxes` | `create_sandbox`, `Sandbox` |
| `eden.sandboxes.no_sandbox` | `provider()` |
| `eden.sandboxes.docker` | `provider(*, image, mounts=None, env=None, network=None)` |
| `eden.errors` | `EdenError` |
| `eden.worktree.errors` | `WorktreeError`, `WorktreeLocked`, `DirtyHostBlocked`, `BranchExists`, `GitCommandFailed` |
| `eden.sandboxes.errors` | `SandboxError`, `ProviderUnavailable`, `ImageNotFound`, `ContainerStartFailed`, `ExecFailed`, `ExecTimeout`, `UnsupportedStrategy` |

### Out of scope (deferred)

- `eden run` and `eden interactive` orchestrators (Phase 3)
- Cloud sandbox providers, Apple containers, Lima, isolated worktrees with `finalize` (Phase 4+)
- `IsolatedSandboxHandle` Protocol + `FinalizeTarget` / `FinalizeResult` types (Phase 4 — ships alongside the first isolated provider)
- Image build pipeline / `eden init` template scaffolding (Phase 6)
- Telemetry / structured logging beyond `print()` (Phase 7)
- tmpfs mounts, named volumes, mount propagation flags

## 2. Provider Protocol design

### 2.1 `BranchStrategy`

```python
StrategyTag = Literal["head", "merge_to_head", "named"]

@dataclass(frozen=True)
class BranchStrategy:
    tag: StrategyTag
    branch: str | None = None
    base: str = "main"

    @staticmethod
    def head() -> "BranchStrategy":
        return BranchStrategy(tag="head")

    @staticmethod
    def merge_to_head(base: str = "main") -> "BranchStrategy":
        return BranchStrategy(tag="merge_to_head", base=base)

    @staticmethod
    def named(branch: str, base: str = "main") -> "BranchStrategy":
        return BranchStrategy(tag="named", branch=branch, base=base)
```

Three strategies:

- **`head`** — reuse the host repo working tree directly. No `git worktree add`. Blocks on dirty host.
- **`merge_to_head`** — carve a managed worktree on an auto-named branch (`eden/<timestamp>-<8hex>`). Default for sandbox providers.
- **`named`** — carve a managed worktree on a caller-specified branch. Fails if branch already exists.

### 2.2 `SandboxProvider`

```python
@runtime_checkable
class SandboxProvider(Protocol):
    name: str
    kind: Literal["bind_mount", "isolated", "none"]

    def supports_strategy(self, strategy: BranchStrategy) -> bool: ...
    def create(self, opts: CreateOptions) -> SandboxHandle: ...
```

`kind` discriminates downstream behavior (e.g., orchestrator finalize logic in Phase 3+). `supports_strategy` lets `create_sandbox` reject unsupported combinations early with `UnsupportedStrategy`.

### 2.3 `CreateOptions`

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

Passed by `create_sandbox` to the provider's `create()`. `branch` is the resolved branch name (post-strategy); `worktree_path` is where the sandbox should operate.

### 2.4 `SandboxHandle` and narrowing

```python
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
    ) -> ExecResult: ...

    def copy_file_in(self, host: Path, sandbox: Path) -> None: ...
    def copy_file_out(self, sandbox: Path, host: Path) -> None: ...
    def close(self) -> None: ...

@runtime_checkable
class BindMountSandboxHandle(SandboxHandle, Protocol):
    """Marker — bind-mount providers don't need extra methods, but the type
    distinguishes them from isolated handles for orchestrator type-narrowing."""
```

Phase 2 ships only `SandboxHandle` and `BindMountSandboxHandle`. `IsolatedSandboxHandle` (with `finalize(target: FinalizeTarget) -> FinalizeResult`) defers to Phase 4 alongside the first isolated provider, so its argument types live there too.

### 2.5 `ExecResult`

```python
@dataclass(frozen=True)
class ExecResult:
    stdout: str
    stderr: str
    exit_code: int

    @property
    def ok(self) -> bool:
        return self.exit_code == 0

    def check(self) -> "ExecResult":
        if not self.ok:
            raise ExecFailed(result=self, argv_or_cmd="<see result>")
        return self
```

`on_line` callback in `exec()` receives interleaved stdout+stderr lines as they arrive; the final `ExecResult` carries the captured full output. Implementation: thread per stream draining into shared `Queue`, line-buffered, single consumer dispatches to `on_line`.

### 2.6 `make_bind_mount_provider`

```python
def make_bind_mount_provider(
    name: str,
    create: Callable[[CreateOptions], BindMountSandboxHandle],
    *,
    supported_strategies: frozenset[StrategyTag] = frozenset(
        {"head", "merge_to_head", "named"}
    ),
) -> SandboxProvider: ...
```

Helper that wraps a `create` function into a full `SandboxProvider` with `kind="bind_mount"`. Used by `no_sandbox` and `docker` modules.

### 2.7 `Mount`

```python
@dataclass(frozen=True)
class Mount:
    host: Path
    sandbox: Path
    read_only: bool = False
```

That's the entire mount surface in Phase 2. No tmpfs, no volumes, no propagation flags.

## 3. Worktree machinery

### 3.1 `create_worktree`

```python
def create_worktree(
    *,
    host_repo_path: Path,
    strategy: BranchStrategy,
    name_hint: str | None = None,
) -> WorktreeHandle: ...
```

Strategy → action:

| Strategy | Action |
|---|---|
| `head` | Verify host clean; acquire `_head.lock`; return handle with `managed=False`, `worktree_path=host_repo_path` |
| `merge_to_head` | Generate branch name `eden/<YYYYMMDDHHMMSS>-<8hex>` (or `eden/<sanitized-name_hint>-<8hex>` if hint given); `git worktree add -b <branch> <worktree_path> <base>`; acquire lock; return managed handle |
| `named` | Verify branch doesn't exist; `git worktree add -b <branch> <worktree_path> <base>`; acquire lock; return managed handle |

Worktree path for managed strategies: `<host_repo_path>/.eden/worktrees/<sanitized-branch>/`.

### 3.2 `WorktreeHandle`

```python
@dataclass(frozen=True)
class WorktreeHandle:
    branch: str
    worktree_path: Path
    host_repo_path: Path
    managed: bool
    _lock_handle: _LockHandle = field(repr=False)

    def __enter__(self) -> "WorktreeHandle":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> "CloseResult": ...
```

`close()` behavior:

- `managed=False` (head): release lock, return `CloseResult(action="released_only")`.
- `managed=True` and worktree clean (`git status --porcelain` empty): run `git worktree remove --force <path>`; release lock; return `CloseResult(action="removed")`.
- `managed=True` and worktree dirty: leave on disk; release lock; emit `print()` warning with path; return `CloseResult(action="preserved", reason="dirty")`.

```python
@dataclass(frozen=True)
class CloseResult:
    action: Literal["removed", "preserved", "released_only"]
    reason: str | None = None
```

### 3.3 Lock implementation

**Lock file location:**

- `head` strategy → `<host_repo_path>/.eden/worktrees/_head.lock`
- Other strategies → `<host_repo_path>/.eden/worktrees/<sanitized-branch>.lock`

**Sanitization:** lowercase, replace runs of `[^a-z0-9._-]` with `-`, strip leading/trailing `-`.

**Mechanism:** native advisory file lock on the lock file's open fd:

- Unix: `fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)`
- Windows: `msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)`

**PID sidecar:** after acquiring the lock, truncate and write `os.getpid()` as decimal text. On release, close the fd (which drops the OS lock) and unlink the file.

**Stale lock recovery:** on `LOCK_EX | LOCK_NB` failure:

1. Read PID from the lock file.
2. `os.kill(pid, 0)` — if `ProcessLookupError`, the holder is dead.
3. Unlink lock file, retry `flock` once.
4. If retry fails or PID is alive, raise `WorktreeLocked(lock_path=path, holder_pid=pid)`.

The recovery dance happens in a small helper (`_acquire_with_recovery`) so behavior is identical across strategies and platforms.

## 4. Sandbox providers

### 4.1 `no_sandbox`

```python
def provider() -> SandboxProvider:
    return make_bind_mount_provider(
        name="no_sandbox",
        create=_create_no_sandbox,
        supported_strategies=frozenset({"head", "merge_to_head", "named"}),
    )
```

`_NoSandboxHandle`:

- `worktree_path` = `opts.worktree_path` (always; never `host_repo_path` even for `head`, since the strategy already resolved them to the same path).
- `exec(cmd, ...)`: `subprocess.Popen(cmd, shell=True, cwd=cwd or self.worktree_path, env=merged_env, stdout=PIPE, stderr=PIPE)`. Stream draining as described in §2.5. Timeout via `Popen.terminate()` then `Popen.kill()` + 5s grace.
- `copy_file_in(host, sandbox)` / `copy_file_out(sandbox, host)`: `shutil.copy2(src, dst)`.
- `close()`: no-op.

### 4.2 `docker`

```python
def provider(
    *,
    image: str,
    mounts: tuple[Mount, ...] | None = None,
    env: Mapping[str, str] | None = None,
    network: str | None = None,
) -> SandboxProvider: ...
```

`image` is **required** — Phase 2 does not build images. The test fixture builds `tests/integration/Dockerfile` once per session.

**`create()` flow:**

1. Verify `docker` binary on PATH (via `shutil.which`); raise `ProviderUnavailable("docker", "docker")` if missing.
2. `docker image inspect <image>` — non-zero → `ImageNotFound(image, stderr)`.
3. Build mount set: `opts.mounts` ∪ provider-level `mounts` ∪ implicit `Mount(host=opts.worktree_path, sandbox=Path("/workspace"))`. Provider-level mounts override on collision (sandbox path key).
4. Build container name: `eden-<sanitized-name_hint or branch>-<8hex>` (truncated to 63 chars).
5. Construct argv:
   ```
   docker run -d --rm -i
     --name <container_name>
     --entrypoint sleep
     [-v <h>:<s>[:ro] ...]
     [-e <K>=<V> ...]
     [--network <network>]
     <image>
     infinity
   ```
6. Capture container ID from stdout; non-zero exit → `ContainerStartFailed(image, exit_code, stderr)`.
7. Return `_DockerHandle(container_id=..., worktree_path=Path("/workspace"), host_worktree_path=opts.worktree_path)`.

**`_DockerHandle`:**

- `exec(cmd, *, on_line, cwd, env, timeout)`:
  ```
  docker exec -i [-w <cwd>] [-e K=V ...] <container_id> /bin/sh -c "<cmd>"
  ```
  Stream draining + timeout flow same as `no_sandbox`. Exit 137 (SIGKILL) after timeout → raise `ExecTimeout` with partial buffers.
- `copy_file_in(host, sandbox)`: `docker cp <host> <container_id>:<sandbox>`.
- `copy_file_out(sandbox, host)`: `docker cp <container_id>:<sandbox> <host>`.
- `close()`: `docker kill <container_id>` (ignores "no such container"); `--rm` handles auto-removal. Idempotent.

### 4.3 `create_sandbox`

```python
def create_sandbox(
    *,
    sandbox: SandboxProvider,
    branch: str | None = None,
    branch_strategy: BranchStrategy | None = None,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    mounts: tuple[Mount, ...] | None = None,
    name: str | None = None,
) -> Sandbox: ...
```

`Sandbox` is a thin context-managing wrapper bundling `WorktreeHandle` + `SandboxHandle` (close in reverse order).

**Argument resolution:**

1. `branch` and `branch_strategy` are mutually exclusive — both set raises `ValueError`.
2. If `branch` is set: `strategy = BranchStrategy.named(branch)`.
3. Else if `branch_strategy` is None: default by `sandbox.kind` — `"none"` → `BranchStrategy.head()`; `"bind_mount"` or `"isolated"` → `BranchStrategy.merge_to_head()`.
4. `if not sandbox.supports_strategy(strategy): raise UnsupportedStrategy(...)`.
5. `wt = create_worktree(host_repo_path=Path.cwd(), strategy=strategy, name_hint=name)`.
6. `handle = sandbox.create(CreateOptions(branch=wt.branch, worktree_path=wt.worktree_path, host_repo_path=wt.host_repo_path, env=env or {}, mounts=mounts or (), name_hint=name))`.
7. Return `Sandbox(worktree=wt, handle=handle)`.

`cwd` parameter is stored on the `Sandbox` for downstream `exec()` calls in Phase 3+; in Phase 2 it's passthrough into the bundled object.

## 5. Error handling

Master spec defines the full hierarchy. Phase 2 ships only:

**Worktree (`eden/worktree/errors.py`):**

| Class | When | Carries |
|---|---|---|
| `WorktreeError(EdenError)` | base | — |
| `WorktreeLocked` | another live PID holds the lock | `lock_path: Path`, `holder_pid: int` |
| `DirtyHostBlocked` | `head` on dirty working tree | `host_repo_path: Path`, `dirty_files: tuple[str, ...]` (first 10) |
| `BranchExists` | `named` and branch exists | `branch: str` |
| `GitCommandFailed` | `git worktree add/remove` non-zero | `argv: tuple[str, ...]`, `exit_code: int`, `stderr: str` |

**Sandbox (`eden/sandboxes/errors.py`):**

| Class | When | Carries |
|---|---|---|
| `SandboxError(EdenError)` | base | — |
| `ProviderUnavailable` | required binary missing | `provider: str`, `binary: str` |
| `ImageNotFound` | `docker image inspect` non-zero | `image: str`, `stderr: str` |
| `ContainerStartFailed` | `docker run` non-zero | `image: str`, `exit_code: int`, `stderr: str` |
| `ExecFailed` | `ExecResult.check()` on failed result | `result: ExecResult`, `argv_or_cmd: str` |
| `ExecTimeout` | command exceeded `timeout=` | `cmd: str`, `timeout: float`, `partial_stdout: str`, `partial_stderr: str` |
| `UnsupportedStrategy` | provider rejects strategy | `provider: str`, `strategy: StrategyTag` |

**Cleanup contract:** every error path that raises after acquiring a resource releases it before re-raising. `WorktreeHandle.__exit__` and `_DockerHandle.close` swallow only `ProcessLookupError` and "no such container"-style noise during cleanup; everything else propagates.

**No silent fallbacks.** Hint strings live in the CLI (Phase 6), not exception messages.

## 6. Test strategy

### 6.1 Layout

```
tests/
├── unit/
│   ├── test_providers_protocol.py
│   ├── test_branch_strategy.py
│   ├── test_worktree_lock.py
│   ├── test_worktree_handle.py
│   ├── test_no_sandbox.py
│   ├── test_docker_provider.py
│   └── test_create_sandbox.py
├── integration/
│   ├── conftest.py                # eden_test_image session fixture
│   ├── Dockerfile                 # alpine + git + bash
│   ├── test_docker_exec.py
│   ├── test_docker_copy.py
│   └── test_docker_lifecycle.py
└── conftest.py                    # tmp git repo, mock_subprocess
```

### 6.2 Unit tests (`unit` marker)

Run on all 9 CI jobs (3 OS × 3 Python). Subprocess calls mocked via a `mock_subprocess` fixture that records argv and returns scripted `(stdout, stderr, exit_code)`. Real-git tests use `tmp_path` + `git init` (<50ms each, no network).

### 6.3 Integration tests (`integration` marker)

Module-level `pytest.skip("docker daemon only available on linux runners")` on macOS/Windows. Linux runners run the full suite against the session-built image.

**`eden_test_image` fixture** (session-scoped):

- Builds `tests/integration/Dockerfile` (alpine + git + bash) once per session.
- Tags as `eden-test:<sha256-of-dockerfile>` for cache reuse.
- Skips entire integration suite if `docker` binary missing or daemon unreachable.

### 6.4 Coverage targets

| Module | Target |
|---|---|
| `eden.providers` | 100% |
| `eden.worktree` | ≥95% (lock recovery + dirty-host paths covered) |
| `eden.sandboxes.no_sandbox` | ≥95% |
| `eden.sandboxes.docker` | ≥85% unit + integration smoke for happy paths |

### 6.5 CI matrix unchanged

9 jobs (Linux/macOS/Windows × 3.11/3.12/3.13). Integration tests no-op skip on macOS/Windows; full run on Linux. Branch protection contexts identical to Phase 1.

### 6.6 Determinism

No test depends on wall-clock time, network, or external registries. Lock-recovery test writes a fake PID sidecar pointing to `2**31 - 1` (definitely-dead PID), asserts recovery succeeds.

## 7. Build-task ordering

Recommended task order for the implementation plan (Phase 2 only — no orchestrator):

1. `eden.errors` base + Phase-2 exception subclasses.
2. `eden.providers` Protocols + dataclasses (`BranchStrategy`, `Mount`, `CreateOptions`, `ExecResult`).
3. `eden.providers.helpers.make_bind_mount_provider`.
4. `eden.worktree._lock` (cross-platform advisory lock with stale-PID recovery).
5. `eden.worktree.create_worktree` + `WorktreeHandle` for `head` strategy.
6. Add `merge_to_head` and `named` strategies + `git worktree` integration.
7. `eden.sandboxes.no_sandbox` provider + handle + tests.
8. `eden.sandboxes.docker` provider + handle (unit-tested with mocked subprocess).
9. `eden.sandboxes.create_sandbox` top-level factory + `Sandbox` wrapper.
10. Integration tests against real Docker.
11. Documentation pass: docstrings on public surface; README status note bumped to "Phase 2 complete."

Each task ends with a green test run + commit.
