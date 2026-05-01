# Eden Phase 4a — Provider Parity (Local) Design

**Status:** Approved design. Implementation to follow via `superpowers:writing-plans`.

**Predecessors:** Phase 2 (sandbox foundations — `docker`, `no_sandbox`, `SandboxProvider` Protocol, `make_bind_mount_provider`). Phase 3a (orchestration core). Phase 3b (Claude Code agent + session capture). Latest commit on main: `ddffc73`.

**Goal:** Bring local sandbox providers to parity. Land `podman` (sibling of `docker`), `isolated` (local patch-sync sandbox), the `IsolatedSandboxHandle` Protocol, `FinalizeResult` typed result, `make_isolated_provider` factory helper, and the shared `make_container_provider` helper that makes docker + podman 5-line factories. Cloud providers (`vercel`, `daytona`) and `http_rest.py` are deferred to Phase 4b.

**Out of scope (deferred to later phases):**
- `vercel(...)` and `daytona(...)` cloud providers (Phase 4b)
- `http_rest.py` cloud helpers (Phase 4b)
- File-mode preservation in patch_sync (e.g., `chmod +x` not preserved) (Phase 5+)
- Empty-directory preservation in patch_sync (Phase 5+)
- `RunResult.merged_to_target_branch` and `RunResult.files_changed` population (Phase 5+)
- Other agents (`codex`, `opencode`, `pi`) (Phase 5)
- CLI scaffolder (Phase 6)

---

## 1. Public surface added

```python
def eden.sandboxes.podman.provider(
    *,
    image: str,
    mounts: tuple[Mount, ...] | None = None,
    env: Mapping[str, str] | None = None,
    network: str | None = None,
) -> SandboxProvider:
    """Podman bind-mount provider — sibling of docker.provider()."""

def eden.sandboxes.isolated.provider(
    *,
    base_dir: Path | None = None,
) -> SandboxProvider:
    """Local isolated provider: copies the worktree to a tmp dir, runs the
    agent there, finalizes by patch-syncing changes back to the host worktree.
    """
```

Re-exported at the top of the `eden` package:

```python
from eden import FinalizeResult, IsolatedSandboxHandle
```

`podman` and `isolated` are accessed via their sub-packages (`eden.sandboxes.podman.provider(...)`, `eden.sandboxes.isolated.provider(...)`) — same pattern as the existing `eden.sandboxes.docker.provider(...)` (no top-level re-export of provider factories).

**`FinalizeResult`** new frozen dataclass:

```python
@dataclass(frozen=True)
class FinalizeResult:
    applied: bool
    files_changed: tuple[Path, ...]
    patch_size_bytes: int
```

**`IsolatedSandboxHandle`** new runtime-checkable Protocol extending `SandboxHandle`:

```python
@runtime_checkable
class IsolatedSandboxHandle(SandboxHandle, Protocol):
    def finalize(self, target: Path) -> FinalizeResult: ...
```

The orchestrator's existing `hasattr(handle, "finalize")` duck-check keeps working; the Protocol is for type-checker narrowing only.

**`make_isolated_provider`** new factory helper (in `eden/providers/_helpers.py`), parallel to `make_bind_mount_provider`:

```python
def make_isolated_provider(
    name: str,
    create: Callable[[CreateOptions], IsolatedSandboxHandle],
    *,
    supported_strategies: frozenset[str] = frozenset({"head", "merge_to_head", "named"}),
) -> SandboxProvider: ...
```

---

## 2. Architecture

### 2.1 New + modified files

```
eden/
├── providers/
│   ├── _types.py                    # MODIFY — add FinalizeResult
│   ├── _protocols.py                # MODIFY — add IsolatedSandboxHandle
│   ├── _helpers.py                  # MODIFY — add make_isolated_provider
│   └── _impl/                       # NEW directory
│       ├── __init__.py              # NEW (empty)
│       ├── container.py             # NEW — make_container_provider (shared docker/podman)
│       └── patch_sync.py            # NEW — snapshot/diff/apply
├── sandboxes/
│   ├── docker/__init__.py           # MODIFY — thin factory over make_container_provider
│   ├── podman/                      # NEW directory
│   │   └── __init__.py              # NEW — thin factory over make_container_provider
│   ├── isolated/                    # NEW directory
│   │   └── __init__.py              # NEW — isolated() factory + _IsolatedHandle
│   └── _factory.py                  # MODIFY (if needed) — wire kind="isolated"
├── orchestrator/
│   ├── _runner.py                   # MODIFY — add optional cwd kwarg to _AgentRunner
│   └── _loop.py                     # MODIFY — call handle.finalize() on success path; pass cwd
└── __init__.py                      # MODIFY — re-export FinalizeResult + IsolatedSandboxHandle

tests/
├── unit/
│   ├── test_container_provider.py       # NEW — mocked argv tests, parametrized over binary
│   ├── test_podman_provider.py          # NEW — small podman factory tests
│   ├── test_patch_sync.py               # NEW — snapshot/diff/apply unit tests
│   ├── test_isolated_provider.py        # NEW — isolated factory + handle lifecycle
│   └── test_finalize_result_types.py    # NEW — FinalizeResult/IsolatedSandboxHandle shape
├── integration/
│   └── test_podman.py                   # NEW — Linux-gated real podman tests
└── e2e/
    └── test_isolated_smoke.py           # NEW — full simulated_agent + isolated + finalize
```

Every new file targets the project's ~300-LoC budget. Largest expected: `_impl/container.py` ~150 LoC.

### 2.2 Per-iteration data flow (isolated)

```
User: eden.run(agent=..., sandbox=isolated(), prompt=...)
        ↓
_run_loop:
  resolve_setup → create_worktree (Phase 2 plumbing for branch strategy)
  sandbox.create(opts):                          ← NEW: kind="isolated" path
    baseline = patch_sync.snapshot(opts.worktree_path)
    isolated_root = base_dir / sanitized_seed-suffix
    shutil.copytree(opts.worktree_path, isolated_root, ignore=[".git", ".eden"])
    return _IsolatedHandle(worktree_path=isolated_root, ...)
        ↓
  _AgentRunner(argv=..., env=..., watchdog=..., cwd=handle.worktree_path)   ← cwd plumbing NEW
        agent process runs in isolated_root
        ↓
  iteration loop completes (success path)
        ↓
  if hasattr(handle, "finalize"):                ← NEW
      finalize_result = handle.finalize(target=wt.host_repo_path)
        # internal: snapshot_after = snapshot(isolated_root)
        # diff = compute_diff(baseline, snapshot_after)
        # apply(diff, src=isolated_root, dst=target)
      sink.write(StreamEvent(text="[eden] finalized: applied=... files=N bytes=M"))
        ↓
  finally:
      handle.close()         # _IsolatedHandle: shutil.rmtree(isolated_root, ignore_errors=True)
      wt.close()
```

### 2.3 Per-iteration data flow (podman)

Identical to docker (Phase 2). `make_container_provider` builds the same argv with `podman` instead of `docker`. The `_ContainerHandle.binary` field carries the binary name; every method (`exec`, `copy_file_in`, `copy_file_out`, `close`) reads it.

### 2.4 Boundaries

- `_impl/container.py` knows about `subprocess` + mount specs. Doesn't know about isolated/finalize.
- `_impl/patch_sync.py` knows about filesystem trees, hashes, and diffs. No subprocess, no sandbox handles.
- `sandboxes/isolated/__init__.py` knows about `shutil.copytree` + `_IsolatedHandle` lifecycle. Glues `patch_sync` to the Protocol.
- `orchestrator/_loop.py` reads `hasattr(handle, "finalize")` and calls it. Doesn't know about patch_sync internals or container details.
- `orchestrator/_runner.py` accepts `cwd` as opaque optional path; doesn't know which sandbox kind passed it.

---

## 3. Component contracts

### 3.1 `make_container_provider`

`eden/providers/_impl/container.py`:

```python
def make_container_provider(
    *,
    binary: Literal["docker", "podman"],
    image: str,
    mounts: tuple[Mount, ...] | None = None,
    env: Mapping[str, str] | None = None,
    network: str | None = None,
) -> SandboxProvider: ...
```

Internally:
- `_ContainerHandle` dataclass carries `binary: str`, `container_id: str`, `worktree_path: Path`, `host_worktree_path: Path`.
- `_create(opts)` mirrors today's `eden/sandboxes/docker/__init__.py:106-168` line-for-line, with every literal `"docker"` in argv lists replaced with `binary`. Container name prefix stays `"eden-..."` (binary distinction is implicit in which CLI is used).
- `ProviderUnavailable(provider=binary, binary=binary)` on missing executable.
- Returns `make_bind_mount_provider(name=binary, create=_create)`.

`_ContainerHandle` methods:
- `exec(cmd, *, on_line=None, cwd=None, env=None, timeout=None) -> ExecResult` — `[binary, "exec", "-i", "-w", cwd.as_posix(), "-e", "K=V", ..., container_id, "/bin/sh", "-c", cmd]` via `stream_exec`.
- `copy_file_in(host, sandbox)` — `[binary, "cp", str(host), f"{container_id}:{sandbox.as_posix()}"]`.
- `copy_file_out(sandbox, host)` — `[binary, "cp", f"{container_id}:{sandbox.as_posix()}", str(host)]`.
- `close()` — `[binary, "kill", container_id]`; idempotent; swallows "no such container" stderr.

### 3.2 `eden/sandboxes/docker/__init__.py` (refactored)

```python
"""docker provider: run commands inside a long-lived docker container."""

from __future__ import annotations

from collections.abc import Mapping

from eden.providers._impl.container import make_container_provider
from eden.providers._protocols import SandboxProvider
from eden.providers._types import Mount


def provider(
    *,
    image: str,
    mounts: tuple[Mount, ...] | None = None,
    env: Mapping[str, str] | None = None,
    network: str | None = None,
) -> SandboxProvider:
    return make_container_provider(
        binary="docker",
        image=image,
        mounts=mounts,
        env=env,
        network=network,
    )


__all__ = ["provider"]
```

### 3.3 `eden/sandboxes/podman/__init__.py`

Identical shape to docker, with `binary="podman"`. ~25 LoC.

### 3.4 `FinalizeResult` (new frozen dataclass in `eden/providers/_types.py`)

```python
@dataclass(frozen=True)
class FinalizeResult:
    """Summary of what `IsolatedSandboxHandle.finalize()` applied to the target."""

    applied: bool
    files_changed: tuple[Path, ...]
    patch_size_bytes: int
```

`applied=True` means every detected change was successfully replayed onto the target. `False` means at least one file copy/unlink failed (failures are logged but `apply` continues with remaining files).

### 3.5 `IsolatedSandboxHandle` Protocol (new in `eden/providers/_protocols.py`)

```python
@runtime_checkable
class IsolatedSandboxHandle(SandboxHandle, Protocol):
    def finalize(self, target: Path) -> FinalizeResult: ...
```

Extends `SandboxHandle` (no field/method removals). The orchestrator uses `hasattr(handle, "finalize")` for the duck-check; this Protocol exists for `isinstance` runtime checks and type-checker narrowing.

### 3.6 `make_isolated_provider` (new in `eden/providers/_helpers.py`)

```python
@dataclass
class _IsolatedProvider:
    name: str
    kind: Literal["isolated"]
    _create_fn: Callable[[CreateOptions], IsolatedSandboxHandle]
    _supported: frozenset[str]

    def supports_strategy(self, strategy: BranchStrategy) -> bool:
        return strategy.tag in self._supported

    def create(self, opts: CreateOptions) -> IsolatedSandboxHandle:
        return self._create_fn(opts)


def make_isolated_provider(
    name: str,
    create: Callable[[CreateOptions], IsolatedSandboxHandle],
    *,
    supported_strategies: frozenset[str] = frozenset({"head", "merge_to_head", "named"}),
) -> SandboxProvider:
    return _IsolatedProvider(
        name=name,
        kind="isolated",
        _create_fn=create,
        _supported=supported_strategies,
    )
```

Mirrors `make_bind_mount_provider`'s shape. The wrapped provider's `kind` is `"isolated"`.

### 3.7 `patch_sync` (new in `eden/providers/_impl/patch_sync.py`)

Three pure functions and one frozen dataclass:

```python
def snapshot(root: Path, *, ignore: tuple[str, ...] = (".git", ".eden")) -> dict[Path, str]:
    """Walk `root`, hash every file's contents (SHA-256), return {relative_path: hex_digest}.

    `ignore` is a tuple of top-level directory names to skip entirely. Returns
    paths relative to `root`. Symlinks are stored with their target paths
    (`os.readlink`) — both contents AND target are part of the hash.
    """


@dataclass(frozen=True)
class DiffResult:
    added: frozenset[Path]
    changed: frozenset[Path]
    removed: frozenset[Path]


def diff(*, before: dict[Path, str], after: dict[Path, str]) -> DiffResult:
    """Compute per-file change sets between two snapshots."""


def apply(diff_result: DiffResult, *, src: Path, dst: Path) -> FinalizeResult:
    """Replay the diff against `dst`:
    - For each path in added | changed: copy src/<path> → dst/<path> (mkdir parents).
    - For each path in removed: unlink dst/<path> (silently if already gone).

    Returns a FinalizeResult summarizing what was applied. Does NOT raise —
    individual file copy/unlink errors are logged and tracked in `applied`.
    """
```

**Hashing:** SHA-256 over file contents (cost is `O(file_size)` per file — same order as the eventual `shutil.copy` cost on apply).

**Limitations (in scope for 4a):**
- File mode (`chmod +x`) NOT preserved.
- Empty directories NOT preserved.
- Hardlinks NOT preserved (each linked file is treated independently).

### 3.8 `eden/sandboxes/isolated/__init__.py`

```python
def provider(*, base_dir: Path | None = None) -> SandboxProvider:
    """Local isolated provider: copy worktree to a tmp dir, run agent there,
    finalize by patch-syncing changes back to the host worktree.

    `base_dir` defaults to `<host_repo_path>/.eden/isolated/` (sibling of
    `.eden/worktrees/` and `.eden/sessions/`). Each `create()` call carves a
    fresh subdirectory there.
    """

    def _create(opts: CreateOptions) -> IsolatedSandboxHandle:
        base = base_dir or (opts.host_repo_path / ".eden" / "isolated")
        base.mkdir(parents=True, exist_ok=True)
        suffix = secrets.token_hex(4)
        seed = opts.name_hint or opts.branch
        isolated_root = base / f"{_sanitize_seed(seed)}-{suffix}"

        baseline = patch_sync.snapshot(opts.worktree_path)
        shutil.copytree(
            opts.worktree_path,
            isolated_root,
            ignore=shutil.ignore_patterns(".git", ".eden"),
        )

        return _IsolatedHandle(
            worktree_path=isolated_root,
            host_worktree_path=opts.worktree_path,
            baseline=baseline,
        )

    return make_isolated_provider(name="isolated", create=_create)


@dataclass
class _IsolatedHandle:
    worktree_path: Path
    host_worktree_path: Path
    baseline: dict[Path, str]

    def exec(self, cmd, *, on_line=None, cwd=None, env=None, timeout=None) -> ExecResult:
        merged_cwd = cwd if cwd is not None else self.worktree_path
        return stream_exec(
            ["/bin/sh", "-c", cmd],
            cmd_for_error=cmd,
            shell=False,
            cwd=str(merged_cwd),
            env=env,
            on_line=on_line,
            timeout=timeout,
        )

    def copy_file_in(self, host: Path, sandbox: Path) -> None:
        shutil.copy(host, sandbox)

    def copy_file_out(self, sandbox: Path, host: Path) -> None:
        shutil.copy(sandbox, host)

    def finalize(self, target: Path) -> FinalizeResult:
        after = patch_sync.snapshot(self.worktree_path)
        d = patch_sync.diff(before=self.baseline, after=after)
        return patch_sync.apply(d, src=self.worktree_path, dst=target)

    def close(self) -> None:
        if self.worktree_path.exists():
            shutil.rmtree(self.worktree_path, ignore_errors=True)
```

`_sanitize_seed` reuses the regex `[^A-Za-z0-9._-]+` (mirrors `eden/logging/_file._BRANCH_SANITIZE`).

`_IsolatedHandle` IGNORES `opts.mounts` — the host filesystem IS the sandbox surface; users who need extra files must `copy_file_in` them after creation.

### 3.9 Orchestrator wiring

#### 3.9.1 `_AgentRunner` cwd kwarg (`eden/orchestrator/_runner.py`)

`__init__` gains `cwd: Path | None = None`; `__enter__` passes `cwd=str(self._cwd) if self._cwd is not None else None` through to `subprocess.Popen`. Default `None` preserves Phase 3a/3b behavior.

#### 3.9.2 `_run_loop` finalize call (`eden/orchestrator/_loop.py`)

Two changes:

1. The `with _AgentRunner(...)` invocation gains a `cwd` argument so `isolated` runs the agent in the carved dir.

   The orchestrator passes `handle.worktree_path` only when that path exists on the host filesystem (via `Path.exists()`). For container providers (docker, podman), `handle.worktree_path` is the in-container path (e.g., `/workspace`) which does NOT exist on the host — `.exists()` returns `False`, the orchestrator falls back to `None`, and the agent (which spawns `docker exec`) inherits the Python process's cwd. For `isolated` and `no_sandbox`, the path exists on the host, so the orchestrator passes it. This avoids adding a new Protocol field for "agent cwd."

   Concretely, `_loop.py` does:
   ```python
   agent_cwd = handle.worktree_path if handle.worktree_path.exists() else None
   with _AgentRunner(argv=argv, env=setup.merged_env, watchdog=wd, cwd=agent_cwd) as runner:
       ...
   ```

2. After the iteration `for` loop's natural completion (success path), and BEFORE the existing `finally:` teardown:

   ```python
   if handle is not None and hasattr(handle, "finalize"):
       try:
           finalize_result = handle.finalize(target=wt.host_repo_path)
           if sink is not None:
               sink.write(StreamEvent(
                   type="text", agent_name=agent.name,
                   iteration=len(iterations),
                   timestamp=_utcnow(),
                   text=(
                       f"[eden] finalized: applied={finalize_result.applied} "
                       f"files={len(finalize_result.files_changed)} "
                       f"bytes={finalize_result.patch_size_bytes}"
                   ),
               ))
       except Exception as exc:
           if sink is not None:
               sink.write(StreamEvent(
                   type="text", agent_name=agent.name,
                   iteration=len(iterations),
                   timestamp=_utcnow(),
                   text=f"[eden] finalize failed: {exc}",
               ))
   ```

   Placement: inside the outer `try:` block. If the iteration loop raised `Aborted`/`IdleTimeout` mid-run, control jumps to `finally:` and skips finalize — the "skip finalize on abort" Q5 contract.

#### 3.9.3 `RunResult` not extended in 4a

`RunResult.merged_to_target_branch` and `files_changed` stay as Phase 5+ work. `FinalizeResult` surfaces only via the synthetic `text` `StreamEvent` (visible in `.eden/logs/...`) and the `on_event` callback.

### 3.10 `create_sandbox` (Phase 2 factory)

Audit `eden/sandboxes/_factory.py` during plan-writing. If `kind="isolated"` is currently unwired, add the dispatch line. If already present, this is a no-op for 4a.

---

## 4. Error handling

| Failure | Behavior | Where caught |
|---|---|---|
| `podman` binary missing | `ProviderUnavailable(provider="podman", binary="podman")` | Propagates out of `eden.run()` |
| podman image missing | `ImageNotFound(image, stderr)` | Propagates |
| podman container start failed | `ContainerStartFailed(image, exit_code, stderr)` | Propagates |
| `isolated` carve fails (disk space, permissions) | `OSError` from `shutil.copytree` | Propagates as-is |
| `isolated` snapshot fails (file disappeared mid-walk) | Skipped silently | Diff treats it as "removed" |
| `isolated` finalize: single file copy fails | `apply()` logs to stderr, sets `applied=False`, continues | Returns `FinalizeResult(applied=False, ...)` |
| `isolated` finalize raises uncaught | `_loop.py`'s `except Exception:` logs `[eden] finalize failed: ...` to sink, continues teardown | Captured in log sink |
| `_AgentRunner` with `cwd=isolated_root`, dir doesn't exist | `FileNotFoundError` from `subprocess.Popen` | Propagates |
| `IsolatedSandboxHandle.close()` called twice | Idempotent (`worktree_path.exists()` is False after first) | Same pattern as Phase 2 |

The "finalize failure is soft" pattern matches Phase 3b's "session capture failure is soft" — agent's work is preserved in stdout/log regardless.

---

## 5. Concurrency

**No new threads.** `snapshot()` and `apply()` run synchronously on the main thread before/after the iteration loop. Phase 3a/3b's stdout-pump and idle-watchdog threading is unchanged.

For container providers, the existing per-call subprocess pattern (one process per `exec`, one process per `cp`) is unchanged.

---

## 6. Testing strategy

### 6.1 Unit tests

| File | Coverage | Approx |
|---|---|---|
| `tests/unit/test_container_provider.py` | Mocked `subprocess.run`/`subprocess.Popen`; parametrized over `binary in ("docker", "podman")`. Argv shape for run/exec/cp/kill, mount and env threading, network flag, name sanitization, error mapping (provider-unavailable, image-not-found, container-start-failed). | ~12 tests |
| `tests/unit/test_podman_provider.py` | `podman.provider(image=...)` returns `SandboxProvider` with `name="podman"`, `kind="bind_mount"`; delegates to `make_container_provider(binary="podman", ...)`. | ~3 tests |
| `tests/unit/test_patch_sync.py` | `snapshot` ignores `.git`/`.eden`, deterministic hashes, symlink target included. `diff` classifies added/changed/removed correctly. `apply` writes added/changed, unlinks removed, populates `FinalizeResult.applied/files_changed/patch_size_bytes`. | ~10 tests |
| `tests/unit/test_isolated_provider.py` | Provider factory returns `kind="isolated"`. `create()` returns handle whose `worktree_path` exists with input contents copied; `close()` removes the dir; idempotent close; `IsolatedSandboxHandle` Protocol structural conformance. | ~6 tests |
| `tests/unit/test_finalize_result_types.py` | `FinalizeResult` is frozen, fields shape; `IsolatedSandboxHandle` is `runtime_checkable` Protocol with the right methods. | ~3 tests |

### 6.2 Integration tests

| File | Coverage |
|---|---|
| `tests/integration/test_podman.py` | Real `podman run` against a small image (alpine); exec, copy_file_in/out, close. Linux-only via `pytest.mark.integration` + `if shutil.which("podman") is None: pytest.skip()`. ~3-4 tests, mirrors `tests/integration/test_docker_*.py`. |

Phase 2's existing `tests/integration/test_docker_*.py` files stay UNCHANGED — they serve as the regression net for the `make_container_provider` extraction.

### 6.3 E2E tests

| File | Coverage |
|---|---|
| `tests/e2e/test_isolated_smoke.py` | `simulated_agent` writes a file inside an `isolated` provider; `eden.run(...)` completes; finalize runs; the file lands in the host worktree; deleting a file in the sandbox propagates to the host; `[eden] finalized: applied=True files=N bytes=M` appears in the log. ~2 tests. |

### 6.4 Coverage

70% gate retained. Existing 94.54% coverage is comfortably maintained.

---

## 7. Backwards compatibility

- All Phase 2 docker tests pass unchanged (the `make_container_provider` extraction is behavior-preserving — verified by the existing integration tests).
- All Phase 3a/3b tests pass unchanged. `_AgentRunner.cwd` defaults to `None` (existing behavior); `_loop.py`'s new `agent_cwd = handle.worktree_path if handle.worktree_path.exists() else None` is additive.
- `bind_mount` providers (docker, podman, no_sandbox) are NOT affected by the new finalize block (`hasattr(handle, "finalize")` is False).
- `_run_loop`'s flow for non-isolated runs is identical pre- and post-4a.

---

## 8. Drop-in promise

The post-3b "agent swap" promise stays intact: replacing `simulated_agent(...)` with `claude_code(model=..., ...)` continues to work. The new "sandbox swap" pattern: replacing `no_sandbox.provider()` or `docker.provider(image=...)` with `isolated.provider()` works identically — the orchestrator detects `finalize` via duck-typing and runs the patch-sync; non-isolated providers see no behavior change.

---

## 9. Phase boundary

**Lands in 4a:** `make_container_provider`, `podman` provider, `isolated` provider, `IsolatedSandboxHandle` Protocol, `FinalizeResult`, `make_isolated_provider`, `patch_sync` module, `_AgentRunner.cwd` extension, `_run_loop` finalize wiring.

**Deferred to 4b:** `vercel` and `daytona` cloud providers, `http_rest.py`.

**Deferred to 5+:** `RunResult.merged_to_target_branch`/`files_changed` population, file-mode preservation, empty-directory preservation, aggregate token usage.

---

**Estimated effort:** ~1.5 weeks, matching the original Phase 4 split.
