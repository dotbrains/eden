# Python API: Types and Streaming

Detailed reference for configuration dataclasses, result types, structured output, and stream events. See [Python API](python-api.md) for the canonical public API index.

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

Log sink for `StreamEvent`s — a file (default) or the host process's stdout. For the file sink, each call to `run()` opens the file in append mode and prepends a `--- Run started: <UTC ISO ts> ---` delimiter so a shared log file remains readable.

```python
@dataclass(frozen=True)
class Logging:
    type: Literal["file", "stdout"]
    path: Path | None = None
    level: Literal["debug", "info", "warn", "error"] = "info"
    on_agent_stream_event: Callable[[StreamEvent], None] | None = None
    verbose: bool = False

    @staticmethod
    def file(
        path: str | Path,
        level: ... = "info",
        on_agent_stream_event: Callable[[StreamEvent], None] | None = None,
        verbose: bool = False,
    ) -> Logging: ...

    @staticmethod
    def stdout(
        level: ... = "info",
        on_agent_stream_event: Callable[[StreamEvent], None] | None = None,
        verbose: bool = False,
    ) -> Logging: ...
```

Use `Logging.file("run.log")` to capture every event the orchestrator emits. Use `Logging.stdout()` to write the same formatted, redacted lines to the host process's stdout instead — useful in CI, where the job log is the natural destination; `RunResult.log_file_path` is `None` for stdout-logged runs. Constructing `Logging(type="file")` without a `path` (or `type="stdout"` with one) raises `InvalidOptions`.

`on_agent_stream_event` (optional) is invoked for every agent-derived event (`text`, `tool_call`, `usage`, `session_id`, and — when `verbose` — `raw`) in addition to sink output. Intended for forwarding the agent's stream to external observability. Idle warnings and orchestrator-internal text are NOT forwarded — use the top-level `on_event` argument to `run()` for those. Errors raised by the callback are swallowed so a broken forwarder cannot kill the run.

`verbose` (optional, default `False`) additionally surfaces each literal, unparsed agent stdout line as a `StreamEvent(type="raw")` — written to the log alongside the human-readable events and forwarded through `on_agent_stream_event`. Lets external observability see the bytes a parser discards (e.g. the JSON envelope behind a `claude --output-format stream-json` line).

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

## Structured output

### `Output`

Helpers for declaring schema-validated payloads on `run()`.

```python
from eden import Output, run

# String tag — extracts trimmed contents of <answer>...</answer>
result = run(..., output=Output.string(tag="answer"), max_iterations=1, prompt="...<answer>...</answer>...")
print(result.output)  # str

# Object tag — JSON-parses contents (with code-fence unwrap) and runs schema()
def parse(raw: object) -> Plan:
    assert isinstance(raw, dict)
    return Plan(**raw)

result = run(..., output=Output.object(tag="plan", schema=parse), max_iterations=1, prompt="...<plan>...</plan>...")
plan = result.output  # whatever schema returned
```

`Output.object(tag, schema)` extracts the **last** `<tag>...</tag>` pair, strips an optional Markdown code fence (`` ```json ... ``` ``), `json.loads` it, and passes the parsed object to `schema`. The `schema` argument can be:

- a **pydantic v2 `BaseModel` class** — Eden invokes `MyModel.model_validate(parsed)` directly, so `schema=MyModel` works without writing `schema=MyModel.model_validate`;
- a **pydantic v1 `BaseModel` class** — detected via `parse_obj` + `__fields__`, invoked as `MyModel.parse_obj(parsed)`;
- a **dataclass / attrs class** wrapped as `schema=lambda d: MyDataclass(**d)`;
- a **msgspec converter** like `schema=lambda d: msgspec.convert(d, MyType)`;
- any other **callable** of shape `(parsed: object) -> T`.

Detection happens at extraction time via `model_validate` / `parse_obj` getattr — no third-party dependencies are imported. Anything that isn't callable and isn't a recognised validator class raises `TypeError` from `eden.output._validator.resolve_validator`.

`Output.string(tag)` extracts the contents and `.strip()`s them — no JSON, no validation.

Validation at entry:
- `max_iterations == 1` is required (raises `InvalidOptions` otherwise).
- `<tag>` must literally appear in the prompt source (raises `InvalidOptions` otherwise).

Failures during extraction raise [`StructuredOutputError`](#structuredoutputerror) with `tag`, `raw_matched`, `branch`, optional `preserved_worktree_path`, and — when the failing iteration was captured — `session_id` and `session_file_path`. The session fields let claude_code callers resume the same conversation with corrective feedback and re-emit corrected output, rather than restart from scratch:

```python
from eden import Output, StructuredOutputError, claude_code, run

try:
    result = run(
        agent=claude_code(),
        sandbox=..., prompt="emit <result>{...}</result>",
        output=Output.object(tag="result", schema=my_schema),
    )
except StructuredOutputError as e:
    if e.session_id is None:
        raise
    run(
        agent=claude_code(),
        sandbox=..., output=Output.object(tag="result", schema=my_schema),
        resume_session=e.session_id,
        prompt=f"Your previous <result> was malformed: {e.raw_matched!r}. Re-emit it.",
    )
```

**`max_retries` automates that loop.** Pass `Output.object(tag=..., schema=..., max_retries=N)` (or `Output.string(tag=..., max_retries=N)`) and `run()` retries on its own when extraction or validation fails: it resumes the failing session with corrective feedback (the failure message + the tag to re-emit), or — for agents without session capture — re-runs the original prompt, up to `N` extra times before raising `StructuredOutputError`. Default `0` (no retry). A negative value raises `InvalidOptions`.

```python
result = run(
    agent=claude_code(),
    sandbox=..., prompt="emit <result>{...}</result>",
    output=Output.object(tag="result", schema=my_schema, max_retries=2),
)
```

### `OutputDefinition`

Type alias for the union of `Output.object(...)` and `Output.string(...)` return values. Use this in helper signatures that accept either shape.

---

## Streaming

### `StreamEvent`

The single discriminated union surfaced by `on_event` and the JSONL log.

```python
@dataclass(frozen=True)
class StreamEvent:
    type: Literal["text", "idle_warning", "tool_call", "usage"]
    agent_name: str
    iteration: int
    timestamp: datetime
    text: str | None = None
    minutes_idle: int | None = None
    tool_name: str | None = None
    tool_input: dict[str, object] | None = None
    usage: Usage | None = None
    session_id: str | None = None
```

The four `type` kinds:

- `"text"` — line of agent output. Carries `text`.
- `"idle_warning"` — emitted on `idle_warning_interval`. Carries `minutes_idle`.
- `"tool_call"` — agent invoked a tool. Carries `tool_name` and `tool_input`.
- `"usage"` — token usage report. Carries `usage` (and optionally `session_id`).

`__post_init__` enforces that the type-specific fields are non-`None`.

---
