# Python API

Reference for everything importable from the top-level `eden` package — every entry-point, dataclass, Protocol, factory, hook type, abort primitive, and error class that `eden.__all__` re-exports.

---

## Importing

Eden's surface is a single module. Import what you need from `eden`; nothing private is part of the contract.

```python
from eden import (
    run, create_worktree,
    RunResult, Iteration, Commit, Usage, Timeouts, Mount, FinalizeResult,
    BranchStrategy, StreamEvent, Logging,
    AbortController, AbortSignal, Aborted,
    Agent, IterationContext,
    simulated_agent, claude_code, codex, opencode, pi, cli_agent,
    Hook, HookPhase, Hooks, HostHooks, SandboxHooks,
    IsolatedSandboxHandle,
    EdenError, ConfigError, CwdError, EdenTimeoutError, EnvMergeError,
    FloxEnvError, HookError, HookFailed, HookTimeout, IdleTimeout, InvalidOptions,
    PromptError, RestAuthError, RestError, RestNotFoundError,
    RestRateLimited, SessionCaptureFailed, StepTimeout,
    __version__,
)
```

Sandbox providers live alongside the public surface but are imported from `eden.providers` (see [sandbox-providers.md](sandbox-providers.md)) — they are passed into `run(sandbox=...)`.

A 15-line minimum-viable example using `simulated_agent` and `no_sandbox`:

```python
from eden import run, simulated_agent
from eden.sandboxes.no_sandbox import provider as no_sandbox

result = run(
    agent=simulated_agent(output="<promise>COMPLETE</promise>\n"),
    sandbox=no_sandbox(),
    prompt="say hi",
    max_iterations=1,
)

print(result.completion_signal)  # "<promise>COMPLETE</promise>"
print(result.branch)              # generated worktree branch
print(len(result.iterations))     # 1
```

---

## Entry points

### `run(...)`

Runs an agent against a sandbox in a managed worktree and returns a `RunResult`. Keyword-only.

```python
def run(
    *,
    agent: Agent,
    sandbox: SandboxProvider,
    prompt: str | None = None,
    prompt_file: str | Path | None = None,
    prompt_args: Mapping[str, str] | None = None,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    branch_strategy: BranchStrategy | None = None,
    max_iterations: int = 1,
    completion_signal: str | list[str] = "<promise>COMPLETE</promise>",
    idle_timeout: float | timedelta = 600.0,
    idle_warning_interval: float | timedelta | None = None,
    name: str | None = None,
    hooks: Hooks | None = None,
    timeouts: Timeouts | None = None,
    on_event: Callable[[StreamEvent], None] | None = None,
    logging: Logging | None = None,
    signal: AbortSignal | None = None,
    output: OutputDefinition | None = None,
    resume_session: str | None = None,
    copy_to_worktree: list[str] | None = None,
    throw_on_duplicate_worktree: bool = True,
) -> RunResult: ...
```

Parameters:

- `agent` — anything satisfying the `Agent` Protocol (see Agents below).
- `sandbox` — a `SandboxProvider` (`no_sandbox()`, `docker(...)`, `daytona(...)`, etc.).
- `prompt` / `prompt_file` / `prompt_args` — supply the iteration prompt inline, from a file path, or with `{name}` substitutions; mutually-aware (see [prompts.md](prompts.md)). Exactly one of `prompt` or `prompt_file` is required.
- `cwd` — host path that will be the worktree root's source. Defaults to `Path.cwd()`.
- `env` — extra environment variables forwarded into the agent process.
- `branch_strategy` — one of `BranchStrategy.head()`, `merge_to_head(base)`, `named(branch, base)`. Defaults to a generated `eden/<slug>` branch.
- `max_iterations` — maximum agent loop iterations. Default `1`.
- `completion_signal` — string or list-of-strings whose appearance in agent output stops the loop early. Default `"<promise>COMPLETE</promise>"`.
- `idle_timeout` — seconds (or `timedelta`) of stdout silence before the run aborts with `IdleTimeout`. Default `600.0`.
- `idle_warning_interval` — emit `StreamEvent(type="idle_warning")` every N seconds during idleness. `None` disables.
- `name` — informational tag used in worktree branch slugs and stream events.
- `hooks` — `Hooks(host=..., sandbox=...)` lifecycle bundle. Default `Hooks()`.
- `timeouts` — `Timeouts(...)` per-step deadlines. Default `Timeouts()`.
- `on_event` — callback invoked with every `StreamEvent`. Use to forward to UIs, logs, or queues.
- `logging` — `Logging.file(path, on_agent_stream_event=...)` to mirror events to a log file, or `Logging.stdout(...)` to write them to the host process's stdout (CI-friendly; `RunResult.log_file_path` is then `None`); the optional callback fires for agent-emitted text/tool_call/usage/session_id events only and swallows exceptions.
- `signal` — `AbortSignal` for cooperative cancellation. If omitted, `run` allocates its own (unused) signal.
- `output` — `Output.object(...)` / `Output.string(...)` to extract a typed payload from a `<tag>` block in stdout. Requires `max_iterations=1` and that `<tag>` literally appear in the prompt. Failure raises [`StructuredOutputError`](#structuredoutputerror).
- `resume_session` — Claude Code session id to resume; appends `--resume <id>` to the agent argv. Requires `max_iterations=1`.
- `copy_to_worktree` — list of host-relative file/directory paths to copy from `cwd` into the freshly-carved worktree before the sandbox boots (and before `host.on_worktree_ready` hooks fire, so hooks can use the copied files). Files preserve their relative path; directories copy recursively; existing destinations are overwritten. Absolute paths, `..` traversal, and the `head` branch strategy raise `InvalidOptions`; missing sources raise `CopyToWorktreeError`. Useful for seeding `.env` files, fixtures, or local configs that the worktree shouldn't inherit from `git checkout`.
- `throw_on_duplicate_worktree` — when `False` and the named-strategy branch already has an on-disk worktree, that worktree is reused (and `close()` does not remove it). Default `True` (raise `BranchExists` on duplicate). Only meaningful for `BranchStrategy.named(...)`. Useful for iterative re-runs against the same scenario branch without `eden clean` in between. On reuse, a clean worktree is fast-forwarded to `origin/<branch>` (`git fetch` + `git merge --ff-only`) so the re-run isn't against stale code; a dirty worktree, a detached HEAD, a missing/unreachable origin, or a diverged branch are all reused as-is.

Returns a `RunResult`.

### Async API

`eden.aio` mirrors the three top-level entry points (`run`, `create_sandbox`, `interactive`) as `async def` functions. Each is a thin `asyncio.to_thread` wrapper around its sync counterpart — same arguments, same return type, no async-native primitives in the core. See [ADR 0011](adr/0011-async-api-surface.md).

```python
import asyncio
import eden
from eden import aio
from eden.sandboxes.no_sandbox import provider as no_sandbox

async def main() -> None:
    # Single run.
    result = await aio.run(
        agent=eden.simulated_agent(output="hi\n<promise>COMPLETE</promise>\n"),
        sandbox=no_sandbox(),
        prompt="x",
        max_iterations=1,
    )

    # Concurrent runs.
    a, b = await asyncio.gather(
        aio.run(agent=..., sandbox=..., prompt="task A", branch_strategy=eden.BranchStrategy.named("eden/a")),
        aio.run(agent=..., sandbox=..., prompt="task B", branch_strategy=eden.BranchStrategy.named("eden/b")),
    )

    # create_sandbox.run() is sync; await it via asyncio.to_thread.
    s = await aio.create_sandbox(sandbox=no_sandbox())
    try:
        impl = await asyncio.to_thread(s.run, agent=..., prompt_file="implement.md", max_iterations=20)
    finally:
        s.close()

asyncio.run(main())
```

Concurrency is bounded by asyncio's default `ThreadPoolExecutor` (`min(32, cpu+4)` workers). Users running more concurrent tasks should size the pool with `loop.set_default_executor(...)`. See [ADR 0011](adr/0011-async-api-surface.md) for why eden does not async-ify the core.

### `interactive(...)`

Run an agent attached to the parent terminal's stdio. There is no iteration loop, no idle watchdog, no completion-signal matching — eden carves a worktree, optionally renders a prompt, and execs the agent. The function returns when the agent process exits.

```python
def interactive(
    *,
    agent: Agent,
    sandbox: SandboxProvider | None = None,
    prompt: str | None = None,
    prompt_file: str | Path | None = None,
    prompt_args: Mapping[str, str] | None = None,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    branch_strategy: BranchStrategy | None = None,
    name: str | None = None,
    hooks: Hooks | None = None,
    copy_to_worktree: list[str] | None = None,
    collect_args: bool | None = None,
) -> InteractiveResult: ...
```

- `sandbox` defaults to `no_sandbox()`. `docker(...)` and `podman(...)` are also supported — eden runs the agent argv inside the container via `<binary> exec -it`. Isolated providers (Daytona, Vercel, the local `isolated` copy) raise `InvalidOptions` because they don't expose a TTY.
- `prompt` / `prompt_file` / `prompt_args` are optional. When supplied, the rendered text is passed to the agent's `build_interactive_command(ctx)` (or `build_command(ctx)` when no interactive override exists).
- `branch_strategy` defaults to `BranchStrategy.head()` when the provider supports it — interactive sessions usually want writes to land in the host repo directly. Override to `merge_to_head()` or `named()` for an isolated session.
- `hooks` runs the same `OnWorktreeReady` / `OnSandboxReady` / `OnClose` lifecycle as `run()`; `OnIterationStart` / `OnIterationEnd` are not relevant.
- `copy_to_worktree` — same semantics as on [`run()`](#run): host-relative paths copied into the worktree before `on_worktree_ready` hooks fire. Incompatible with `BranchStrategy.head()`, which is the default for interactive sessions — pass `branch_strategy=BranchStrategy.merge_to_head()` (or `named(...)`) to use it.
- `collect_args` — when the rendered prompt references `{{KEY}}` placeholders not supplied via `prompt_args`, eden prompts the user via stdin for each missing key instead of raising `PromptError`. Defaults to autodetect: collect when `stdin` is a TTY, skip otherwise (so CI runs hit the normal error). Pass `True` / `False` to force.

Returns an [`InteractiveResult`](#interactiveresult).

### `InteractiveResult`

```python
@dataclass(frozen=True)
class InteractiveResult:
    branch: str
    exit_code: int
    worktree_path: Path
    cwd: Path
```

Lightweight: `exit_code` is the agent's exit status; `branch` is the worktree branch (`"HEAD"` for the head strategy); `worktree_path` is where the agent ran (commit / inspect from there). No commit list, no stdout — interactive sessions don't capture either.

### `create_sandbox(...)`

Creates a sandbox + worktree once and returns a `Sandbox` whose `.run(...)` method can be called multiple times against the same branch and container. Use when one logical task requires multiple agent runs (implement → review, plan → execute, etc.) and you want them to share environment, branch, and any provider-side caches.

```python
def create_sandbox(
    *,
    sandbox: SandboxProvider,
    branch: str | None = None,
    branch_strategy: BranchStrategy | None = None,
    worktree: WorktreeHandle | None = None,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    mounts: tuple[Mount, ...] | None = None,
    name: str | None = None,
    copy_to_worktree: list[str] | None = None,
    timeouts: Timeouts | None = None,
) -> Sandbox: ...
```

`worktree` (when supplied) reuses a caller-managed `WorktreeHandle` from [`create_worktree()`](#create_worktree) instead of carving a fresh one. Ownership is then split: `Sandbox.close()` tears down the container only, and the caller's `worktree.close()` decides the worktree's fate (preserved if dirty, removed if clean) — so one worktree can host several sequential sandboxes. Mutually exclusive with `branch`/`branch_strategy`/`base_branch`.

```python
with eden.create_worktree(branch="eden/feature/x") as wt:
    with eden.create_sandbox(sandbox=docker_provider(...), worktree=wt) as s:
        s.run(agent=eden.claude_code("..."), prompt_file="implement.md")
    # First container is gone; the branch and its files are still on disk.
    with eden.create_sandbox(sandbox=docker_provider(image="review:latest"), worktree=wt) as s:
        s.run(agent=eden.claude_code("..."), prompt_file="review.md")
```

`copy_to_worktree` (when supplied) seeds host-relative files into the worktree before the sandbox boots — same semantics as on [`run()`](#run), and the copy happens once at `create_sandbox()` time (not on every subsequent `sb.run()`). Incompatible with `BranchStrategy.head()`.

`timeouts` caps the one-time carve's git plumbing via `Timeouts.git_setup` (reused by `Sandbox.close()` for the teardown `git worktree remove`). Per-run deadlines like `iteration_step` are passed separately to each [`Sandbox.run(timeouts=...)`](#sandboxrun).

The returned `Sandbox` is a dataclass with `.worktree`, `.handle`, `.sandbox_provider`, `.cwd`, `.owns_worktree`, plus a `.run(...)` method (same shape as the top-level `run()` minus `agent`/`sandbox` already supplied). It also doubles as a context manager — `with create_sandbox(...) as s:` closes the handle, and the worktree too when the sandbox carved it itself (`owns_worktree=True`; `False` for caller-provided worktrees).

### `Sandbox.run(...)`

Run an agent against an already-created sandbox. Same arguments as `run()` minus `sandbox=` (already bound) and `branch_strategy=` (would be ignored — the sandbox already owns a branch). All other options carry over: `output=`, `resume_session=`, `logging=`, `on_event=`, `signal=`, `hooks=`, `timeouts=`, etc.

Useful for sequential-reviewer / planner-executor patterns where multiple agents share one branch, and for resuming a captured Claude Code session in a fresh container without re-creating the worktree.

```python
with eden.create_sandbox(sandbox=docker_provider(...), branch="eden/feature/x") as s:
    impl = s.run(agent=eden.claude_code("..."), prompt_file="implement.md", max_iterations=20)
    if impl.commits:
        s.run(agent=eden.claude_code("..."), prompt_file="review.md", max_iterations=1)
```

### `create_worktree(...)`

Carves a worktree without launching an agent — useful when you want to manage the iteration loop yourself.

```python
def create_worktree(
    *,
    branch: str | None = None,
    branch_strategy: BranchStrategy | None = None,
    name: str | None = None,
) -> WorktreeHandle: ...
```

Provide either `branch` (named) or `branch_strategy` (any of the three strategies); supplying both raises `ValueError`. Defaults to `BranchStrategy.merge_to_head()`. Returns a `WorktreeHandle` with `.branch`, `.worktree_path`, and `.close()` (works as a context manager).

Pass the handle to [`create_sandbox(worktree=...)`](#create_sandbox) to host one or more sequential sandboxes on it without giving up ownership — each `Sandbox.close()` removes only its container; the worktree lives until your `wt.close()`.

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
- `git_setup` — per-command budget for the host-side git plumbing `run()` runs while carving and tearing down a worktree (`git worktree add`/`remove`, branch/worktree listing, `status`, and the `origin` fast-forward when reusing a clean worktree). Exceeded → `GitCommandTimeout`. Raise it on slow filesystems (NFS, networked volumes) or large repos where worktree creation legitimately takes longer than 60s. Honored by `run()`, `interactive()`, and `create_sandbox(timeouts=...)`; the standalone `create_worktree()` helper carves at the 60s default (pass `git_timeout=` to override).
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

    @staticmethod
    def file(
        path: str | Path,
        level: ... = "info",
        on_agent_stream_event: Callable[[StreamEvent], None] | None = None,
    ) -> Logging: ...

    @staticmethod
    def stdout(
        level: ... = "info",
        on_agent_stream_event: Callable[[StreamEvent], None] | None = None,
    ) -> Logging: ...
```

Use `Logging.file("run.log")` to capture every event the orchestrator emits. Use `Logging.stdout()` to write the same formatted, redacted lines to the host process's stdout instead — useful in CI, where the job log is the natural destination; `RunResult.log_file_path` is `None` for stdout-logged runs. Constructing `Logging(type="file")` without a `path` (or `type="stdout"` with one) raises `InvalidOptions`.

`on_agent_stream_event` (optional) is invoked for every agent-derived event (`text`, `tool_call`, `usage`, `session_id`) in addition to sink output. Intended for forwarding the agent's stream to external observability. Idle warnings and orchestrator-internal text are NOT forwarded — use the top-level `on_event` argument to `run()` for those. Errors raised by the callback are swallowed so a broken forwarder cannot kill the run.

### `Mount`

Provider-side bind-mount declaration (used by sandbox providers, not by `run` directly).

```python
@dataclass(frozen=True)
class Mount:
    host: Path
    sandbox: Path
    read_only: bool = False
```

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

## Agents

### `Agent` Protocol

Structural contract every agent must satisfy. Runtime-checkable.

```python
@runtime_checkable
class Agent(Protocol):
    @property
    def name(self) -> str: ...
    @property
    def model(self) -> str: ...
    def build_command(self, ctx: IterationContext) -> list[str]: ...
    def parse_stream(self, line: str) -> StreamEvent | None: ...
```

Agents may also expose `captures_sessions: bool` — the orchestrator reads it via `getattr` and post-processes session JSONL when `True`.

### `IterationContext`

Passed into `Agent.build_command(ctx)`.

```python
@dataclass(frozen=True)
class IterationContext:
    iteration: int
    prompt: str
    sandbox_handle: SandboxHandle
    worktree_path: Path
    branch: str
    name: str | None
```

### Factories

Six factories ship in-tree. Each returns an `Agent`. See [agents.md](agents.md) for capability comparisons.

Every CLI-backed factory (`claude_code`, `codex`, `opencode`, `pi`, `cursor`, `copilot`, `cli_agent`) accepts an optional `flox_env: str | Path | None = None`. When set to a directory containing a Flox env (`.flox/env/manifest.toml`), the orchestrator runs that agent's CLI inside it via `flox activate -d <dir> -- <argv>`, giving each agent type its own declared, lockfile-pinned toolchain. Enforced when present: a missing manifest or `flox` binary raises [`FloxEnvError`](#errors); set `EDEN_ALLOW_NO_FLOX=1` to skip activation where Flox is unavailable. See [agents.md](agents.md#per-agent-flox-runtime) and ADR-0014.

#### `simulated_agent(...)`

```python
def simulated_agent(
    name: str = "simulated",
    model: str = "deterministic-1",
    *,
    output: str | list[str] | Callable[[IterationContext], str] = "<promise>COMPLETE</promise>\n",
    delay_per_line: float = 0.0,
    fail_with: Exception | None = None,
) -> Agent: ...
```

A deterministic agent that emits a pre-baked output. Use in tests, in examples, or when wiring up the orchestrator without an LLM.

#### `claude_code(...)`

```python
def claude_code(
    model: str = "claude-opus-4-7",
    *,
    name: str = "claude-code",
    effort: Literal["low", "medium", "high"] | None = None,
    env: Mapping[str, str] | None = None,
    capture_sessions: bool = True,
    dangerously_skip_permissions: bool = False,
    permission_mode: Literal["default", "acceptEdits", "plan", "bypassPermissions"] | None = None,
    extra_args: tuple[str, ...] = (),
) -> Agent: ...
```

Wraps the Claude Code CLI; sets `captures_sessions=True` so the orchestrator preserves session JSONLs under `.eden/sessions/`. Pass `extra_args` for any CLI flag eden does not yet surface.

`permission_mode` gives graduated tool-approval control via `--permission-mode <mode>` (`"default"`, `"acceptEdits"`, `"plan"`, `"bypassPermissions"`) — a middle ground between prompting on every tool and the all-or-nothing `dangerously_skip_permissions`. The two are mutually exclusive; passing `permission_mode` alongside `dangerously_skip_permissions=True`, or an unrecognised mode, raises `InvalidOptions(code="config.invalid_options")`. Mirrors sandcastle's `claudeCode(model, { permissionMode })`. See [agents.md](agents.md#claude_code) for the per-mode semantics.

When `capture_sessions=True`, the agent ships a [`session_storage`](#session-storage) attribute of type `ClaudeSessionStorage` that the orchestrator delegates transcript capture to. Out-of-tree agents (codex, pi, opencode wrappers, etc.) can mirror this pattern to plug in their own transcript layout — see the `SessionStorage` Protocol below.

#### `codex(...)`

```python
def codex(
    model: str = "gpt-5",
    *,
    env: Mapping[str, str] | None = None,
    extra_args: tuple[str, ...] = (),
) -> Agent: ...
```

Thin wrapper over `cli_agent` for the OpenAI Codex CLI binary. Default `model="gpt-5"` is illustrative.

#### `opencode(...)`

```python
def opencode(
    model: str = "claude-opus-4",
    *,
    env: Mapping[str, str] | None = None,
    extra_args: tuple[str, ...] = (),
) -> Agent: ...
```

Wrapper for `sst/opencode`. Default `model="claude-opus-4"` is illustrative — opencode supports many providers.

#### `pi(...)`

```python
def pi(
    model: str = "pi-3.5",
    *,
    env: Mapping[str, str] | None = None,
    extra_args: tuple[str, ...] = (),
) -> Agent: ...
```

Wrapper for the `pi` CLI binary.

#### `cursor(...)`

```python
def cursor(
    model: str = "claude-sonnet-4-6",
    *,
    name: str = "cursor",
    env: Mapping[str, str] | None = None,
    force: bool = False,
    extra_args: tuple[str, ...] = (),
) -> Agent: ...
```

Wrapper for Cursor's CLI binary (named `agent`). Builds `agent --print --output-format stream-json --model <model> [--force] [extra_args ...] <prompt>`. Prompt is delivered positionally, with a 120 KB pre-flight guard (raises `InvalidOptions(code="config.prompt_too_long")` on overflow). `force` is Cursor's equivalent of Claude's `dangerously_skip_permissions`. `captures_sessions` is `False`. The parser handles cursor's `tool_call` event and delegates Claude-compatible `assistant`/`result` blocks to Claude's parser. See [agents.md](agents.md#cursor) for details.

#### `copilot(...)`

```python
def copilot(
    model: str = "claude-sonnet-4",
    *,
    name: str = "copilot",
    effort: Literal["low", "medium", "high"] | None = None,
    env: Mapping[str, str] | None = None,
    allow_all_tools: bool = False,
    extra_args: tuple[str, ...] = (),
) -> Agent: ...
```

Wrapper for the `copilot` CLI binary (GitHub Copilot CLI). Builds `copilot -p <prompt> --output-format json --model <model> [--allow-all-tools] [--effort <level>] [extra_args ...]`. Prompt is delivered via `-p` (still argv), with the same 120 KB pre-flight guard. `allow_all_tools` is Copilot's equivalent of Claude's `dangerously_skip_permissions`. `captures_sessions` is `False`. The parser decodes `assistant.message_delta` → `text`, `tool.execution_start` → `tool_call` (normalises lowercase `"bash"` → `"Bash"`), `result` → `session_id`, `error`/`agent_error` → `text`. See [agents.md](agents.md#copilot) for details.

#### `cli_agent(...)`

Generic factory for any line-streaming CLI. The codex/opencode/pi wrappers are 5-line shims over this.

```python
def cli_agent(
    *,
    name: str,
    model: str,
    binary: str,
    build_argv: Callable[[IterationContext], list[str]] | None = None,
    parse_stream: Callable[[str], StreamEvent | None] | None = None,
    captures_sessions: bool = False,
    env: Mapping[str, str] | None = None,
    extra_args: tuple[str, ...] = (),
) -> Agent: ...
```

- `name` — `StreamEvent.agent_name`.
- `model` — informational; threaded into argv if your `build_argv` references it.
- `binary` — executable resolved through `$PATH` at spawn.
- `build_argv` — override the default `[binary, *extra_args, ctx.prompt]`.
- `parse_stream` — override the default `None` (orchestrator emits `text` events per line).
- `captures_sessions` — opt-in session post-processing.
- `env` — per-agent env additions (merged by the orchestrator).
- `extra_args` — appended between binary and prompt by the default `build_argv`.

### <a id="session-storage"></a>`SessionStorage` Protocol

```python
@runtime_checkable
class SessionStorage(Protocol):
    def extra_mounts(self) -> tuple[Mount, ...]: ...
    def host_capture(
        self, *, handle, session_id, host_repo_path, branch, iteration
    ) -> Path | None: ...
    def sandbox_transfer(self, *, handle, host_session_file, session_id) -> None: ...
```

Per-agent transcript capture, ADR-0012 style. Eden's default Claude Code agent ships a `ClaudeSessionStorage` instance on its `session_storage` attribute (set when `capture_sessions=True`), which the orchestrator delegates to instead of doing the work in `_run_loop`. Out-of-tree agents (codex, pi, opencode wrappers) can ship their own `SessionStorage` implementation to plug in custom transcript layouts without forking the orchestrator. Legacy agents that only expose `captures_sessions: bool` still work — the orchestrator falls back to `ClaudeSessionStorage` for them.

### `ClaudeSessionStorage`

```python
@dataclass(frozen=True)
class ClaudeSessionStorage:
    home: Path | None = None
```

The default `SessionStorage` implementation, used by `claude_code()`. Mounts `~/.claude/projects` into containerized sandboxes and locates Claude's per-iteration JSONL by the project-slug convention. `home=` overrides `~` for tests.

### `CodexSessionStorage`

```python
@dataclass(frozen=True)
class CodexSessionStorage:
    home: Path | None = None
```

The `SessionStorage` implementation used by `codex(capture_sessions=True)` (the default). Mounts `~/.codex/sessions` into containerized sandboxes and walks codex's date-nested directory tree (`<YYYY>/<MM>/<DD>/rollout-<timestamp>-<session_id>.jsonl`) to locate the per-iteration transcript. `home=` overrides `~` for tests.

### `PiSessionStorage`

```python
@dataclass(frozen=True)
class PiSessionStorage:
    home: Path | None = None
```

The `SessionStorage` implementation used by `pi(capture_sessions=True)` (the default). Mounts `~/.pi/agent/sessions` into containerized sandboxes and locates pi's per-iteration JSONL by the `--<encoded-cwd>--/<timestamp>_<session_id>.jsonl` convention. Resume rewrites the session header's `cwd` field via `transfer_pi_session(...)` and places the JSONL inside the sandbox-cwd-encoded directory so pi's project-first resolver doesn't trigger the "fork session?" prompt. `home=` overrides `~` for tests.

### `transfer_session`

```python
def transfer_session(
    *,
    source: Path,
    dest: Path,
    source_cwd: str,
    dest_cwd: str,
) -> Path: ...
```

Cross-host helper. Copies a captured session JSONL from `source` to `dest`, rewriting every absolute path that starts with `source_cwd` to start with `dest_cwd`. Use to migrate captured sessions between machines whose worktree paths differ (e.g. `/Users/alice/repo` → `/home/build/repo`) so the resumed agent sees its own filesystem layout. `dest`'s parent is created. Raises `SessionCaptureFailed` on missing source or I/O error.

---

## Lifecycle hooks

Eden runs commands at five named phases — `HookPhase` enumerates them and `Hooks` bundles host-side and sandbox-side variants.

### `Hook`

```python
@dataclass(frozen=True)
class Hook:
    cmd: str
    cwd: Path | None = None
    env: Mapping[str, str] | None = None
    timeout: float | None = None
```

A single shell command to run. `timeout=None` defers to `Timeouts.hook_step`.

### `HookPhase`

```python
class HookPhase(Enum):
    OnWorktreeReady = "on_worktree_ready"
    OnSandboxReady = "on_sandbox_ready"
    OnIterationStart = "on_iteration_start"
    OnIterationEnd = "on_iteration_end"
    OnClose = "on_close"
```

Order: `OnWorktreeReady` (host) → `OnSandboxReady` (sandbox) → for each iteration `OnIterationStart` → agent → `OnIterationEnd` → on exit `OnClose`.

### `HostHooks`

```python
@dataclass(frozen=True)
class HostHooks:
    on_worktree_ready: tuple[Hook, ...] = ()
    on_iteration_start: tuple[Hook, ...] = ()
    on_iteration_end: tuple[Hook, ...] = ()
    on_close: tuple[Hook, ...] = ()
```

Host hooks run sequentially on the workstation. Note: `on_sandbox_ready` is sandbox-only.

### `SandboxHooks`

```python
@dataclass(frozen=True)
class SandboxHooks:
    on_sandbox_ready: tuple[Hook, ...] = ()
    on_iteration_start: tuple[Hook, ...] = ()
    on_iteration_end: tuple[Hook, ...] = ()
    on_close: tuple[Hook, ...] = ()
```

Sandbox hooks run inside the sandbox handle. They may execute in parallel where the provider supports it.

### `Hooks`

```python
@dataclass(frozen=True)
class Hooks:
    host: HostHooks = field(default_factory=HostHooks)
    sandbox: SandboxHooks = field(default_factory=SandboxHooks)
```

Failure mapping: a hook that exits non-zero raises `HookFailed`; exceeding its `timeout` raises `HookTimeout`. Both are subclasses of `HookError`.

---

## Cancellation

Cooperative cancellation uses an `AbortController` / `AbortSignal` pair. Pass the signal to `run(signal=...)`; call `controller.abort()` from another thread to stop.

### `AbortController`

```python
@dataclass
class AbortController:
    signal: AbortSignal = field(default_factory=AbortSignal)

    def abort(self, *, reason: str = "abort-signal") -> None: ...
```

Writer side. `abort()` is idempotent — only the first call records a `reason`.

### `AbortSignal`

```python
@dataclass
class AbortSignal:
    def is_aborted(self) -> bool: ...
    @property
    def reason(self) -> str | None: ...
    def raise_if_aborted(self) -> None: ...
    def wait(self, timeout: float | None = None) -> bool: ...
```

Reader side. Pollable via `is_aborted()`, blocking via `wait(timeout)`, and assertable via `raise_if_aborted()` (raises `Aborted`).

### `Aborted`

```python
class Aborted(EdenError):
    def __init__(self, *, reason: str = "abort-signal") -> None: ...
```

Raised by `raise_if_aborted()` and surfaced from `run()` when cancellation lands.

### `register_shutdown(callback)`

```python
def register_shutdown(callback: ShutdownCallback) -> Callable[[], None]: ...
```

Register a synchronous teardown that runs on `SIGINT`, `SIGTERM`, or normal process exit. Returns an idempotent unregister function. The first registration installs a single process-wide handler per signal; the last unregistration removes it.

Use this when you create resources that need to be released even when the parent process is killed without running `try/finally` (most notably `SIGTERM`). `eden.run()` already wires its own teardown for the sandbox handle and worktree it creates — `register_shutdown` is for caller-managed cleanup (e.g. a cloud workspace allocated outside `eden.run()`).

`callback` must be synchronous and tolerate running in a signal context. Exceptions raised from one callback are swallowed; the rest still run.

### `ShutdownCallback`

```python
ShutdownCallback = Callable[[], None]
```

Type alias for `register_shutdown` callbacks.

---

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

## Display

A swappable sink abstraction for orchestrator → user output. Eden re-exports the Protocol and three concrete sinks; pass any of them to higher-level CLI / interactive helpers that accept a `display=` argument. Ports sandcastle's tagged `DisplayEntry` ADT (`src/Display.ts`).

### `Display`

```python
class Display(Protocol):
    def intro(self, title: str) -> None: ...
    def status(self, message: str, severity: Severity = "info") -> None: ...
    def text(self, message: str) -> None: ...
    def tool_call(self, name: str, formatted_args: str) -> None: ...
    def summary(self, title: str, rows: Mapping[str, str]) -> None: ...
    @contextmanager
    def spinner(self, message: str) -> Iterator[None]: ...
    @contextmanager
    def task_log(self, title: str) -> Iterator[Callable[[str], None]]: ...
```

`Severity` is one of `"info" | "success" | "warn" | "error"`. The two context managers wrap long-running blocks: `spinner` for an indeterminate progress indicator; `task_log` for collecting per-step messages and emitting them on exit (the yielded callable pushes messages into the log).

### `DisplayEntry`

Tagged-union of `IntroEntry | StatusEntry | SpinnerEntry | SummaryEntry | TaskLogEntry | TextEntry | ToolCallEntry`. Each has a `.tag` literal and the relevant payload fields. Used by `SilentDisplay` to record everything for test assertions.

### `SilentDisplay`

```python
display = SilentDisplay()
# ... orchestrator runs ...
assert display.entries[-1].title == "Run complete"
```

Records every entry on `.entries`, prints nothing. The test sink.

### `FileDisplay`

```python
display = FileDisplay(Path(".eden/logs/run.log"))
```

Append-only file sink with timestamped delimiter on construction. Spinners and task logs record their duration. Suitable for unattended / CI runs.

### `RichDisplay`

```python
display = RichDisplay()  # uses default rich.console.Console()
```

Live terminal output powered by the bundled `rich` dependency. Renders severities with color glyphs, spinners with `rich.status.Status`, summaries as bold-key / dim-value blocks. Inject a custom `Console` via `RichDisplay(console=Console(file=...))` for capturing tests.

---

## Errors

Every error eden raises descends from `EdenError`. Each concrete class accepts a `cause` keyword argument and carries `code`, `message`, and `hint` attributes for structured logging. `EdenTimeoutError` additionally subclasses the built-in `TimeoutError` for mixed-`except` ergonomics. See [errors.md](errors.md) for the full taxonomy with `code` strings, raise sites, and recovery guidance.

### `format_error_message(error)`

```python
from eden import EdenError, format_error_message, run

try:
    run(agent=..., sandbox=..., prompt="...")
except EdenError as e:
    print(format_error_message(e))
```

Maps any `EdenError` (including the sandbox / worktree subclasses) to a single multi-line user-friendly string of the form:

    <kind-prefix>: <message>
      code: <code>
      hint: <hint>

`hint` is preserved when the error already carries one (e.g. `InvalidOptions(..., hint=...)`). For tagged provider errors that don't carry a hint — `ProviderUnavailable`, `ImageNotFound`, `ContainerStartFailed`, `ExecTimeout`, etc. — the formatter synthesises a context-aware suggestion ("Is Docker running?", "Build the image first: `docker build ...`", "Increase `Timeouts.iteration_step`"). Use this in CLI surfaces so users get the same recovery message regardless of which error subclass surfaced.

The 20 concrete error classes re-exported from `eden`:

- `EdenError` — base class for everything.
- `AgentError` — the agent subprocess exited non-zero without hitting the completion signal. Carries `agent_name`, `exit_code`, `stderr`, and `parsed_error` (extracted from stdout for Codex / Pi / OpenCode, which surface errors there rather than on stderr).
- `ConfigError` — bad arguments, env, or cwd; raised before any side-effect.
- `CopyToWorktreeError` — a worktree copy failed. Raised in two places: (1) the isolated provider's worktree clone failed or exceeded `Timeouts.copy_to_worktree`; (2) a `copy_to_worktree=` entry passed to `run()` / `create_sandbox()` / `interactive()` doesn't exist on disk, or the copy hit a permissions / disk-space error. Carries `source`, `target`, `timeout`, and `timed_out` (true on budget overrun, false on missing-source / permission / disk failure).
- `CwdError` — invalid `cwd=` (missing, not a directory, not in a git repo).
- `EdenTimeoutError` — base for time-budget exceedances; subclasses `TimeoutError`.
- `EnvMergeError` — conflicting `env` overrides between caller, agent, and provider.
- `FloxEnvError` — an agent declared a `flox_env` that can't be activated: the directory has no `.flox/env/manifest.toml`, or the `flox` binary isn't on `PATH`. Raised before the first iteration (fail-fast). Set `EDEN_ALLOW_NO_FLOX=1` to skip activation when `flox` is unavailable. Code `config.flox_env`.
- `HookError` — base for hook failures.
- `HookFailed` — a hook command exited non-zero.
- `HookTimeout` — a hook exceeded `Timeouts.hook_step` (or its own `timeout`).
- `IdleTimeout` — agent stdout was silent past `idle_timeout`.
- `InvalidOptions` — generic kwarg validation failure.
- `PromptError` — `prompt`/`prompt_file`/`prompt_args` resolution failed.
- `RestAuthError` — 401/403 from a cloud provider's REST API.
- `RestError` — base for any non-2xx REST response (or `status=0` connection failure).
- `RestNotFoundError` — 404 from a cloud provider.
- `RestRateLimited` — 429 after retries were exhausted.
- `SessionCaptureFailed` — the orchestrator could not locate or read a session JSONL; soft failure surfaced as a warning event.
- `SessionNotFound` — raised at run start when `resume_session=<id>` references a JSONL that does not exist on the host filesystem. The orchestrator runs this precheck before spawning the agent so the failure surfaces host-side with the expected path, rather than buried in agent stderr. Carries `session_id`, `agent_name`, optional `expected_path`, and `hint`.
- `StepTimeout` — an iteration exceeded `Timeouts.iteration_step`.
- <a id="structuredoutputerror"></a>`StructuredOutputError` — `output=Output.{object,string}(...)` failed to extract or validate. Carries `tag`, `raw_matched` (the matched contents or `None`), `branch`, optional `preserved_worktree_path`, and — when the failing iteration was captured — `session_id` and `session_file_path` so claude_code callers can resume that conversation with corrective feedback via `resume_session=`. Raised on missing tag, invalid JSON, or schema validation failure.

---

## Tracing

Eden emits OpenTelemetry spans for the iteration loop, sandbox lifecycle, hooks, and REST requests. The runtime depends on `opentelemetry-api>=1.20`; without an installed SDK, OTel's no-op tracer makes every span a zero-cost noop. To collect traces in your application, install `opentelemetry-sdk` and configure a provider/exporter — eden picks up whatever provider is set globally.

Spans emitted:

| Span | Where | Key attributes |
| --- | --- | --- |
| `eden.run` | one per `eden.run()` / `eden.aio.run()` call | `agent.name`, `agent.model`, `sandbox.name`, `sandbox.kind`, `branch`, `max_iterations`, `caller_managed`, `iterations`, `completion_signal` |
| `eden.sandbox.create` | wraps `Sandbox.create` + `OnSandboxReady` hooks | `sandbox.name`, `sandbox.kind`, `branch` |
| `eden.agent.exec` | one per agent invocation (per iteration) | `agent.name`, `agent.model`, `iteration.index`, `branch` |
| `eden.hook` | one per host or sandbox hook command | `hook.location` (`host`/`sandbox`), `hook.phase`, `hook.command`, `hook.timeout_s` |
| `eden.rest.request` | one per `RestClient` HTTP request | `http.method`, `http.url`, `http.status_code`, `http.retry_count` |

All spans record exceptions via `Span.record_exception()` and set status to `ERROR` on raise — failures show up in your trace UI without extra wiring.

Every span also emits two metrics derived from its name:

- `<span>.count` — counter, attribute `outcome` ∈ `{ok, error}`.
- `<span>.duration_seconds` — histogram, same `outcome` attribute.

So `eden.run.count{outcome="error"}` gives you the failure rate across runs, and `eden.agent.exec.duration_seconds` (P50/P95) tells you whether iterations are getting slower over time. Wire up an OTel `MeterProvider` alongside the `TracerProvider` to receive them.

A minimal SDK setup for local debugging:

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor

provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(provider)

import eden
eden.run(agent=..., sandbox=..., prompt="...")
```

See [ADR 0012](adr/0012-otel-tracing.md) for the design rationale and instrumented site list.

---

## Version

### `__version__`

```python
import eden
print(eden.__version__)
```

`eden.__version__` exposes the installed package version (read via `importlib.metadata`). Unit tests assert the value matches `pyproject.toml`.
