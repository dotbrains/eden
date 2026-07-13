# Python API: Results

Detailed reference for result dataclasses returned by runs, worktrees, and
isolated-provider finalization. See [Python API: Types](python-api-types.md) for
configuration dataclasses.

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

`removed` means Eden deleted a clean managed worktree. `preserved` means the
worktree was dirty and left on disk for inspection. `released_only` means there
was no owned worktree to remove, or it had already been closed.

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

`completion_signal` is the matched signal that stopped the loop, or `None` if
all iterations ran to completion. `commits` lists the commits the agent created
on the run's branch, newest first, censused after the run via `git rev-list
base..HEAD`; see [`Timeouts.commit_collection`](python-api-types.md#timeouts).
Bind-mount providers preserve the agent's commits on disk, so this reflects
them directly. Isolated/cloud providers patch-sync file changes only, so
`commits` is empty there even when the agent committed inside the sandbox.
`merged_to_target_branch` is reserved for a future merge-back step and is
currently always `None`. `usage` is the final iteration's token usage. `output`
is the validated payload extracted by `output=Output.object(...)` /
`Output.string(...)`, or `None` when no `output=` is configured.

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

One entry per executed iteration. `session_id` and `session_file_path` are
populated when the agent reports `captures_sessions=True`.

### `Commit`

```python
@dataclass(frozen=True)
class Commit:
    sha: str
```

Captured commit on the worktree branch, populated in order they appeared.

### `Usage`

Token-accounting numbers from agents that report them, such as Claude Code.

```python
@dataclass(frozen=True)
class Usage:
    input_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int
    output_tokens: int
```

### `FinalizeResult`

Returned by `IsolatedSandboxHandle.finalize(target)`.

```python
@dataclass(frozen=True)
class FinalizeResult:
    applied: bool
    files_changed: tuple[Path, ...]
    patch_size_bytes: int
```

`applied=False` means at least one copy or unlink failed; the orchestrator logs
failures and continues.
