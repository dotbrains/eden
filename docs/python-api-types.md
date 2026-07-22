# Python API: Types

Detailed reference for configuration dataclasses. See
[Python API: Logging](python-api-logging.md) for `Logging`,
[Python API: Streaming](python-api-streaming.md) for `StreamEvent`, and
[Python API: Results](python-api-results.md) for result dataclasses. See
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
- `commit_collection` — seconds budget for the post-run `git rev-list base..HEAD` that censuses the commits the agent made on the branch (populates [`RunResult.commits`](python-api-results.md#runresult)). Bounded separately from `git_setup` because it runs after the agent and may walk a long history. Best-effort: a timeout (or any git error) yields no commits rather than raising, so a slow census never sinks an otherwise-good run. Raise it on large repos where the walk legitimately exceeds 60s.

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

Container providers expand `~` in `host` paths before launching the runtime.
They also resolve `sandbox` paths: absolute paths are used as-is, paths
beginning with `~` expand under `/home/agent`, and relative paths resolve under
`/workspace`.

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

## Result types

Moved to [Python API: Results](python-api-results.md#result-types).

Compatibility anchors:
<a id="closeresult"></a><a id="runresult"></a><a id="iteration"></a><a id="commit"></a><a id="usage"></a><a id="finalizeresult"></a>

---

## <a id="structured-output"></a><a id="output"></a><a id="outputdefinition"></a>Structured output

Moved to [Python API: Structured output](python-api-output.md#structured-output).

---

## Streaming

Moved to [Python API: Streaming](python-api-streaming.md#streaming).

Compatibility anchors: <a id="streaming"></a><a id="streamevent"></a>

- [`StreamEvent`](python-api-streaming.md#streamevent)

---
