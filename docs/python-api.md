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
    HookError, HookFailed, HookTimeout, IdleTimeout, InvalidOptions,
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
- `logging` — `Logging.file(path, on_agent_stream_event=...)` to mirror events to a log file; the optional callback fires for agent-emitted text/tool/usage events only and swallows exceptions.
- `signal` — `AbortSignal` for cooperative cancellation. If omitted, `run` allocates its own (unused) signal.
- `output` — `Output.object(...)` / `Output.string(...)` to extract a typed payload from a `<tag>` block in stdout. Requires `max_iterations=1` and that `<tag>` literally appear in the prompt. Failure raises [`StructuredOutputError`](#structuredoutputerror).
- `resume_session` — Claude Code session id to resume; appends `--resume <id>` to the agent argv. Requires `max_iterations=1`.

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
) -> InteractiveResult: ...
```

- `sandbox` defaults to `no_sandbox()`. `docker(...)` and `podman(...)` are also supported — eden runs the agent argv inside the container via `<binary> exec -it`. Isolated providers (Daytona, Vercel, the local `isolated` copy) raise `InvalidOptions` because they don't expose a TTY.
- `prompt` / `prompt_file` / `prompt_args` are optional. When supplied, the rendered text is passed to the agent's `build_interactive_command(ctx)` (or `build_command(ctx)` when no interactive override exists).
- `branch_strategy` defaults to `BranchStrategy.head()` when the provider supports it — interactive sessions usually want writes to land in the host repo directly. Override to `merge_to_head()` or `named()` for an isolated session.
- `hooks` runs the same `OnWorktreeReady` / `OnSandboxReady` / `OnClose` lifecycle as `run()`; `OnIterationStart` / `OnIterationEnd` are not relevant.

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
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    mounts: tuple[Mount, ...] | None = None,
    name: str | None = None,
) -> Sandbox: ...
```

The returned `Sandbox` is a dataclass with `.worktree`, `.handle`, `.sandbox_provider`, `.cwd`, plus a `.run(...)` method (same shape as the top-level `run()` minus `agent`/`sandbox` already supplied). It also doubles as a context manager — `with create_sandbox(...) as s:` closes the handle and worktree on exit.

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

---

## Configuration types

### `Timeouts`

Frozen dataclass capping per-step durations.

```python
@dataclass(frozen=True)
class Timeouts:
    hook_step: float = 60.0
    iteration_step: float | None = None
```

- `hook_step` — seconds budget for any individual hook command. Exceeded → `HookTimeout`.
- `iteration_step` — seconds budget for one agent iteration. `None` defers to `idle_timeout`. Exceeded → `StepTimeout`.

### `Logging`

File sink for `StreamEvent`s. Each call to `run()` opens the file in append mode and prepends a `--- Run started: <UTC ISO ts> ---` delimiter so a shared log file remains readable.

```python
@dataclass(frozen=True)
class Logging:
    type: Literal["file"]
    path: Path
    level: Literal["debug", "info", "warn", "error"] = "info"
    on_agent_stream_event: Callable[[StreamEvent], None] | None = None

    @staticmethod
    def file(
        path: str | Path,
        level: ... = "info",
        on_agent_stream_event: Callable[[StreamEvent], None] | None = None,
    ) -> Logging: ...
```

Use `Logging.file("run.log")` to capture every event the orchestrator emits.

`on_agent_stream_event` (optional) is invoked for every agent-derived event (`text`, `tool_call`, `usage`) in addition to file output. Intended for forwarding the agent's stream to external observability. Idle warnings and orchestrator-internal text are NOT forwarded — use the top-level `on_event` argument to `run()` for those. Errors raised by the callback are swallowed so a broken forwarder cannot kill the run.

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

`completion_signal` is the matched signal that stopped the loop (or `None` if all iterations ran to completion). `merged_to_target_branch` is set when a `merge_to_head` strategy successfully merged. `usage` is the final iteration's token usage. `output` is the validated payload extracted by `output=Output.object(...)` / `Output.string(...)`, or `None` when no `output=` is configured.

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

`Output.object(tag, schema)` extracts the **last** `<tag>...</tag>` pair, strips an optional Markdown code fence (`` ```json ... ``` ``), `json.loads` it, and calls `schema(parsed)`. `schema` is any `Callable[[object], T]` that returns a validated value or raises — works with pydantic `Model.model_validate`, dataclass factories, msgspec, or hand-rolled validators.

`Output.string(tag)` extracts the contents and `.strip()`s them — no JSON, no validation.

Validation at entry:
- `max_iterations == 1` is required (raises `InvalidOptions` otherwise).
- `<tag>` must literally appear in the prompt source (raises `InvalidOptions` otherwise).

Failures during extraction raise [`StructuredOutputError`](#structuredoutputerror) with `tag`, `raw_matched`, `branch`, and optional `preserved_worktree_path` so callers can recover commits and worktree state.

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
    model: str,
    *,
    name: str = "claude-code",
    effort: Literal["low", "medium", "high"] | None = None,
    env: Mapping[str, str] | None = None,
    capture_sessions: bool = True,
    extra_args: tuple[str, ...] = (),
) -> Agent: ...
```

Wraps the Claude Code CLI; sets `captures_sessions=True` so the orchestrator preserves session JSONLs under `.eden/sessions/`. Pass `extra_args` for any CLI flag eden does not yet surface.

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

---

## Provider Protocol re-export

### `IsolatedSandboxHandle`

Eden re-exports `IsolatedSandboxHandle` so consumers can build cloud or out-of-tree providers without depending on `eden.providers._protocols` directly.

```python
@runtime_checkable
class IsolatedSandboxHandle(SandboxHandle, Protocol):
    def finalize(self, target: Path) -> FinalizeResult: ...
```

A `SandboxHandle` whose state replicates back to the host on close via `finalize(target)`. The orchestrator detects the protocol via `hasattr(handle, "finalize")`. Bind-mount providers (docker, podman, no_sandbox) do not implement it. See [custom-providers.md](custom-providers.md) for the full protocol surface.

---

## Errors

Every error eden raises descends from `EdenError`. Each concrete class accepts a `cause` keyword argument and carries `code`, `message`, and `hint` attributes for structured logging. `EdenTimeoutError` additionally subclasses the built-in `TimeoutError` for mixed-`except` ergonomics. See [errors.md](errors.md) for the full taxonomy with `code` strings, raise sites, and recovery guidance.

The 17 concrete error classes re-exported from `eden`:

- `EdenError` — base class for everything.
- `ConfigError` — bad arguments, env, or cwd; raised before any side-effect.
- `CwdError` — invalid `cwd=` (missing, not a directory, not in a git repo).
- `EdenTimeoutError` — base for time-budget exceedances; subclasses `TimeoutError`.
- `EnvMergeError` — conflicting `env` overrides between caller, agent, and provider.
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
- `StepTimeout` — an iteration exceeded `Timeouts.iteration_step`.
- <a id="structuredoutputerror"></a>`StructuredOutputError` — `output=Output.{object,string}(...)` failed to extract or validate. Carries `tag`, `raw_matched` (the matched contents or `None`), `branch`, and optional `preserved_worktree_path`. Raised on missing tag, invalid JSON, or schema validation failure.

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
