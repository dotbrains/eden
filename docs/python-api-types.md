# Python API: Types

Detailed reference for configuration and result dataclasses. See
[Python API: Logging](python-api-logging.md) for `Logging`,
[Python API: Streaming](python-api-streaming.md) for `StreamEvent`, and
[Python API](python-api.md) for the canonical public API index.

---

## Configuration types

### `Timeouts`

Frozen dataclass capping per-step durations.

```python
@dataclass(frozen=True)
class Timeouts:
    hook_step: float = 60.0
    iteration_step: float | None = None
    copy_to_worktree: float = 60.0
    git_setup: float = 60.0
    commit_collection: float = 60.0
```

- `hook_step` — seconds budget for any individual hook command. Exceeded → `HookTimeout`.
- `iteration_step` — seconds budget for one agent iteration. `None` defers to `idle_timeout`. Exceeded → `StepTimeout`.
- `copy_to_worktree` — seconds budget for the isolated provider's worktree clone. Exceeded → `CopyToWorktreeError(timed_out=True)`. Set the provider's own `copy_timeout` to override per-call; pass `None` to disable the budget.
- `git_setup` — per-command budget for the host-side git plumbing `run()` runs while carving and tearing down a worktree (`git worktree add`/`remove`, branch/worktree listing, `status`, and the `origin` fast-forward when reusing a clean worktree). Exceeded → `GitCommandTimeout`. Raise it on slow filesystems (NFS, networked volumes) or large repos where worktree creation legitimately takes longer than 60s. Honored by `run()`, `interactive()`, `create_sandbox(timeouts=...)`, and standalone `create_worktree(timeouts=Timeouts(git_setup=...))`.
- `commit_collection` — seconds budget for the post-run `git rev-list base..HEAD` that censuses the commits the agent made on the branch (populates [`RunResult.commits`](#runresult)). Bounded separately from `git_setup` because it runs after the agent and may walk a long history. Best-effort: a timeout (or any git error) yields no commits rather than raising, so a slow census never sinks an otherwise-good run. Raise it on large repos where the walk legitimately exceeds 60s.

### `Logging`

Moved to [Python API: Logging](python-api-logging.md#logging).

Compatibility anchor: <a id="logging"></a>

### `Mount`

Provider-side bind-mount declaration (used by sandbox providers, not by `run` directly).

```python
@dataclass(frozen=True)
class Mount:
    host: Path
    sandbox: Path
    read_only: bool = False
```

Container providers resolve `sandbox` paths before launching the runtime:
absolute paths are used as-is, paths beginning with `~` expand under
`/home/agent`, and relative paths resolve under `/workspace`.

### `BranchStrategy`

Frozen dataclass with three named constructors describing how the worktree branch relates to `base`:

```python
@dataclass(frozen=True)
class BranchStrategy:
    tag: Literal["head", "merge_to_head", "named"]
    branch: str | None = None
    base: str = "main"

    @staticmethod
    def head() -> BranchStrategy: ...
    @staticmethod
    def merge_to_head(base: str = "main") -> BranchStrategy: ...
    @staticmethod
    def named(branch: str, base: str = "main") -> BranchStrategy: ...
```

- `head()` — work directly on the current `HEAD`; no merge, no auto-named branch.
- `merge_to_head(base)` — generated branch off `base`; merged back on success.
- `named(branch, base)` — explicit branch off `base`; preserved as-is.

---

## Result types

### `CloseResult`

Returned by `WorktreeHandle.close()` and `Sandbox.close()`.

```python
@dataclass(frozen=True)
class CloseResult:
    action: Literal["removed", "preserved", "released_only"]
    reason: str | None = None
```

`removed` means Eden deleted a clean managed worktree. `preserved` means the worktree was dirty and left on disk for inspection. `released_only` means there was no owned worktree to remove, or it had already been closed.

### `RunResult`

Returned by `run()`. Frozen dataclass.

```python
@dataclass(frozen=True)
class RunResult:
    iterations: list[Iteration]
    completion_signal: str | None
    branch: str
    stdout: str
    commits: list[Commit]
    worktree_path: Path
    preserved_worktree_path: Path | None
    merged_to_target_branch: str | None
    cwd: Path
    prompt: str
    env: dict[str, str]
    log_file_path: Path | None
    session_id: str | None
    session_file_path: Path | None
    usage: Usage | None
    output: object | None = None
```

`completion_signal` is the matched signal that stopped the loop (or `None` if all iterations ran to completion). `commits` lists the commits the agent created on the run's branch, newest first — censused after the run via `git rev-list base..HEAD` (see [`Timeouts.commit_collection`](#timeouts)). Bind-mount providers (`no_sandbox`, `docker`, `podman`) preserve the agent's commits on disk, so this reflects them directly; isolated/cloud providers patch-sync file changes only (no commit history returns to the host worktree), so `commits` is empty there even when the agent committed inside the sandbox — inspect `worktree_path`/`stdout` instead. `merged_to_target_branch` is reserved for a future merge-back step and is currently always `None` (Eden leaves the branch in place for review rather than merging it to HEAD). `usage` is the final iteration's token usage. `output` is the validated payload extracted by `output=Output.object(...)` / `Output.string(...)`, or `None` when no `output=` is configured.

### `Iteration`

```python
@dataclass(frozen=True)
class Iteration:
    index: int
    completion_signal: str | None
    session_id: str | None
    session_file_path: Path | None
    usage: Usage | None
```

One entry per executed iteration. `session_id` and `session_file_path` are populated when the agent reports `captures_sessions=True`.

### `Commit`

```python
@dataclass(frozen=True)
class Commit:
    sha: str
```

Captured commit on the worktree branch — populated in order they appeared.

### `Usage`

Token-accounting numbers from agents that report them (e.g. Claude Code).

```python
@dataclass(frozen=True)
class Usage:
    input_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int
    output_tokens: int
```

### `FinalizeResult`

Returned by `IsolatedSandboxHandle.finalize(target)` — summarises what the cloud/isolated provider replayed onto the host.

```python
@dataclass(frozen=True)
class FinalizeResult:
    applied: bool
    files_changed: tuple[Path, ...]
    patch_size_bytes: int
```

`applied=False` means at least one copy or unlink failed; the orchestrator logs failures and continues.

---

## <a id="structured-output"></a><a id="output"></a><a id="outputdefinition"></a>Structured output

Moved to [Python API: Structured output](python-api-output.md#structured-output).

---

## Streaming

Moved to [Python API: Streaming](python-api-streaming.md#streaming).

Compatibility anchors: <a id="streaming"></a><a id="streamevent"></a>

- [`StreamEvent`](python-api-streaming.md#streamevent)

---
