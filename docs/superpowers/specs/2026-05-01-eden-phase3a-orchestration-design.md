# Eden Phase 3a — Orchestration Core Design

**Status:** Approved 2026-05-01
**Phase:** 3a of 7 in the [Eden Python rewrite](2026-04-30-eden-python-rewrite-design.md) (Phase 3 split into 3a + 3b)
**Effort estimate:** ~1.5 weeks
**Predecessor:** [Phase 2 — Sandbox Foundations](2026-05-01-eden-phase2-sandbox-foundations-design.md)
**Successor:** Phase 3b — Claude Code agent + session capture

## 1. Scope & deliverables

Phase 3a lands the orchestration substrate that connects Phase 2's sandbox/worktree foundations to a top-level public `run()` entry. Every piece needed to drive an iteration loop is delivered, but the only agent it can drive in this phase is the deterministic `simulated_agent`. Phase 3b drops in `claude_code(...)` plus session capture without changing 3a's public shape.

### Phase 3 split rationale

The master spec budgets Phase 3 at ~3 weeks. The natural seam is:

- **3a (this spec)** — orchestration foundations that work with simulated agents (~1.5 weeks).
- **3b (separate spec)** — Claude Code agent + session JSONL capture, plugging into 3a's `Agent` Protocol (~1.5 weeks).

The split mirrors the `EDEN_AGENT_EXEC_MODE=simulated` toggle that the master design already calls out, makes per-phase review tractable, and sets the pattern Phase 5 (codex / opencode / pi) reuses.

### Public surface added in this phase

| Module | Exposes |
|---|---|
| `eden` | `run`, `create_worktree`, `simulated_agent`, `Agent`, `BranchStrategy` (re-export), `Hook`, `Hooks`, `HostHooks`, `SandboxHooks`, `Logging`, `Timeouts`, `Mount` (re-export), `RunResult`, `Iteration`, `StreamEvent`, `Usage`, `Commit`, `AbortController`, `AbortSignal`, `Aborted`, `EdenError` (re-export), plus all new error subclasses listed in `eden.errors` |
| `eden.errors` (extended) | `InvalidOptions`, `PromptError`, `EnvMergeError`, `CwdError`, `HookFailed`, `HookTimeout`, `EdenTimeoutError`, `IdleTimeout`, `StepTimeout`, `Aborted` |
| `eden.prompt` | `render_prompt(...)` helper for direct use; internal modules `_source` / `_render` / `_shell` |
| `eden.lifecycle` | `Hook`, `Hooks`, `HostHooks`, `SandboxHooks`, `HookPhase` |
| `eden.orchestrator` | `run`, `create_worktree` (re-exported on top-level `eden`) |
| `eden.agents` | `simulated_agent`, `Agent` Protocol, `IterationContext` |
| `eden.streaming` | `StreamEvent`, `TextDeltaBuffer` |
| `eden.abort` | `AbortController`, `AbortSignal` |
| `eden.logging` | `Logging` (file sink only in 3a) |
| `eden.env` | `merge_env` (internal) |

### Out of scope (deferred)

- `eden.agents.claude_code` — Phase 3b
- `eden.session.store` (Claude JSONL session capture + cwd rewrite) — Phase 3b
- `interactive(...)` public entry — Phase 3b
- `wt.run(...)` / `wt.interactive(...)` / `wt.create_sandbox(...)` compound methods on `Worktree` — Phase 3b
- `resume_session=` and `copy_to_worktree=` kwargs on `run()` — Phase 3b
- `RunResult.commits` / `RunResult.merged_to_target_branch` population — Phase 3b
- `RunResult.session_id` / `session_file_path` / `usage` population — Phase 3b
- `StreamEvent(type="tool_call", ...)` — Phase 3b
- `Logging.stdout(...)` rich-rendered TUI — Phase 3b
- `.eden/.env` file loader and agent-env layering — Phase 3b
- `eden run` / `eden interactive` / `eden docker` CLI commands — Phase 6
- Codex / Opencode / Pi agents — Phase 5
- Podman / Vercel / Daytona / isolated providers — Phase 4
- `IsolatedSandboxHandle` Protocol + `FinalizeTarget` / `FinalizeResult` — Phase 4
- Telemetry / structured-log JSON / OTEL — not in v1
- Async (`arun`) variant — not in v1

## 2. Public API

### 2.1 Top-level `eden` exports added in 3a

```python
from eden import (
    # entrypoints
    run,
    create_worktree,
    # agent factories (3a: simulator only — Claude in 3b)
    simulated_agent,
    # protocols + types
    Agent,
    BranchStrategy,                              # re-exported from Phase 2
    Hook,
    Hooks,
    HostHooks,
    SandboxHooks,
    Logging,
    Timeouts,
    Mount,                                       # re-exported from eden.providers
    RunResult,
    Iteration,
    StreamEvent,
    Usage,
    Commit,
    AbortController,
    AbortSignal,
    Aborted,
    # errors
    EdenError,
    InvalidOptions,
    PromptError,
    EnvMergeError,
    CwdError,
    HookFailed,
    HookTimeout,
    EdenTimeoutError,
    IdleTimeout,
    StepTimeout,
)
```

### 2.2 `run(...)` signature (3a subset)

```python
def run(
    *,
    agent: Agent,                                # 3a: only simulated_agent(...) is supplied; Claude in 3b
    sandbox: SandboxProvider,                    # any Phase 2 provider (no_sandbox, docker)
    prompt: str | None = None,
    prompt_file: str | Path | None = None,       # exactly one of prompt/prompt_file
    prompt_args: dict[str, str] | None = None,
    cwd: str | Path | None = None,
    env: dict[str, str] | None = None,
    branch_strategy: BranchStrategy | None = None,
    max_iterations: int = 1,
    completion_signal: str | list[str] = "<promise>COMPLETE</promise>",
    idle_timeout: float | timedelta = 600.0,
    idle_warning_interval: float | timedelta | None = None,
    name: str | None = None,
    hooks: Hooks | None = None,
    timeouts: Timeouts | None = None,
    on_event: Callable[[StreamEvent], None] | None = None,
    logging: Logging | None = None,              # default: Logging.file(".eden/logs/<branch>-<utc>.log")
    signal: AbortSignal | None = None,
) -> RunResult: ...
```

**Deferred from master signature (3b territory):** `resume_session`, `copy_to_worktree`. Both add cleanly as kwargs in 3b without breaking callers.

### 2.3 `simulated_agent(...)` factory

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

`output` is the deterministic stream content. `delay_per_line` exercises idle-timer code paths in unit tests without sleeping seconds. `fail_with` triggers spawn-failure code paths. Single factory covers every test scenario in §4.7.

### 2.4 `create_worktree(...)` signature

```python
def create_worktree(
    *,
    branch: str | None = None,
    branch_strategy: BranchStrategy | None = None,
    name: str | None = None,
) -> Worktree: ...
```

Returns a context-manager `Worktree` with `.branch`, `.worktree_path`, `.close() -> CloseResult`. Wraps Phase 2's `WorktreeHandle`. **3a does not** add `wt.run(...)` / `wt.interactive(...)` / `wt.create_sandbox(...)` — those compound methods are 3b.

### 2.5 Validation rules (`InvalidOptions` raised before any side effect)

Validation runs synchronously, top to bottom, before any worktree carve, sandbox spawn, or log file open:

1. Exactly one of `prompt`/`prompt_file` (xor) — else `InvalidOptions(code="config.invalid_options")`.
2. `prompt_args` is only valid with `prompt_file` — else `InvalidOptions`.
3. `prompt_args` reserved keys `SOURCE_BRANCH` / `TARGET_BRANCH` rejected — else `InvalidOptions`.
4. `branch_strategy` (if explicit) must be supported by `sandbox.kind` — else `UnsupportedStrategy` (Phase 2 error).
5. Caller `env` must not collide with provider `env` — else `EnvMergeError`.
6. `cwd` (if given) must exist and be a git repo — else `CwdError`.

## 3. Internal architecture

### 3.1 Module layout

```
eden/
├── __init__.py                    # NEW exports — see §2.1
├── _types.py                      # NEW: shared frozen dataclasses (Usage, Commit, Mount-public, etc.)
├── agents/
│   ├── __init__.py                # NEW: simulated_agent factory + Agent Protocol re-export
│   ├── _protocol.py               # NEW: Agent Protocol — name, model, build_command, parse_stream
│   ├── _context.py                # NEW: IterationContext dataclass
│   └── simulated.py               # NEW: deterministic SimulatedAgent
├── prompt/
│   ├── __init__.py                # NEW: render_prompt(...) public helper
│   ├── _source.py                 # NEW: PromptSource (Inline | File) resolution + xor validation
│   ├── _render.py                 # NEW: {{KEY}} substitution + built-ins
│   └── _shell.py                  # NEW: !`cmd` shell-block expansion via handle.exec
├── lifecycle/
│   ├── __init__.py                # NEW: Hook, Hooks, HostHooks, SandboxHooks
│   ├── _phases.py                 # NEW: HookPhase enum
│   └── _runner.py                 # NEW: run_host_hooks (sequential), run_sandbox_hooks (parallel)
├── orchestrator/
│   ├── __init__.py                # NEW: run() and create_worktree() public entries
│   ├── _loop.py                   # NEW: _run_loop(...) imperative iteration driver
│   ├── _completion.py             # NEW: completion-signal substring matcher
│   ├── _idle.py                   # NEW: idle-timer + warning emitter
│   ├── _runner.py                 # NEW: agent runner — spawns subprocess, pumps stdout via thread+queue
│   ├── _setup.py                  # NEW: validation pipeline
│   └── _result.py                 # NEW: RunResult assembly
├── env/
│   ├── __init__.py                # NEW: merge_env (internal)
│   └── _merge.py                  # NEW: layered merge with EnvMergeError
├── logging/
│   ├── __init__.py                # NEW: Logging dataclass + factories
│   ├── _file.py                   # NEW: file-sink writer (newline-delimited plain text)
│   ├── _redact.py                 # NEW: secret redactor
│   └── _format.py                 # NEW: log line formatter
├── streaming/
│   ├── __init__.py                # NEW: StreamEvent + TextDeltaBuffer
│   └── _buffer.py                 # NEW: TextDeltaBuffer
├── abort/
│   ├── __init__.py                # NEW: AbortController, AbortSignal, Aborted
│   └── _signal.py                 # NEW: threading.Event wrapper
├── errors.py                      # MODIFY: add new exception subclasses (see §4.1)
└── ...                            # Phase 2 modules unchanged
```

`~300 LoC ceiling per file` (master-spec rule). Names prefixed `_` are internal; only `__init__.py` files re-export public names.

### 3.2 Agent Protocol (3a minimal)

```python
@runtime_checkable
class Agent(Protocol):
    name: str
    model: str

    def build_command(self, ctx: IterationContext) -> list[str]: ...
    def parse_stream(self, line: str) -> StreamEvent | None: ...
```

`supports_resume()` and `supports_session_capture()` from the master spec are **deferred to 3b** — they're only meaningful once a real agent (Claude) is in the picture. Adding methods to a Protocol later is a non-breaking change.

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

### 3.3 Iteration loop (`eden.orchestrator._loop._run_loop`)

```
1. Setup (synchronous, no side effects yet)
   - validate kwargs                       → InvalidOptions
   - resolve cwd, prompt source, env merge → InvalidOptions / EnvMergeError / CwdError
   - resolve branch_strategy from kwargs   (head | merge_to_head | named)

2. Carve worktree                          [ Phase 2 create_worktree ]
   - run host hooks: OnWorktreeReady       (sequential)

3. Open sandbox                            [ Phase 2 sandbox.create ]
   - run sandbox hooks: OnSandboxReady     (parallel)

4. Open log sink                           (Logging.file → .eden/logs/...)

5. for i in range(max_iterations):
       run host hooks:    OnIterationStart  (sequential)
       run sandbox hooks: OnIterationStart  (parallel)

       prompt_text = render_prompt(source, args, built-ins, shell-blocks via handle.exec)

       agent_argv = agent.build_command(IterationContext(iteration=i, prompt=prompt_text, ...))

       with _AgentRunner(agent, argv=agent_argv, sandbox=handle) as runner:
           # Background thread pumps stdout lines → Queue.
           # Idle watchdog (threading.Event + Timer) wakes main thread on:
           #   (a) stdout activity     → reset idle deadline
           #   (b) idle_warning_interval elapsed → emit StreamEvent(type="idle_warning")
           #   (c) idle_timeout elapsed → raise IdleTimeout
           # AbortSignal checked at every queue poll → raise Aborted.

           for line in runner.iter_lines(idle_timeout, idle_warning_interval, signal):
               event = agent.parse_stream(line) or StreamEvent(type="text", text=line, ...)
               log_sink.write(event)
               if on_event: on_event(event)
               if completion_match(line, completion_signal):
                   completion_signal_hit = line
                   runner.terminate()
                   break

       run sandbox hooks: OnIterationEnd    (parallel)
       run host hooks:    OnIterationEnd    (sequential)

       iterations.append(Iteration(index=i, completion_signal=..., session_id=None,
                                   session_file_path=None, usage=None))
       if completion_signal_hit:
           break

6. Teardown (always — try/finally)
   - run sandbox hooks: OnClose            (parallel)
   - run host hooks:    OnClose            (sequential)
   - sandbox.close()
   - log_sink.close()
   - wt.close() → CloseResult.preserved_worktree_path

7. Return RunResult(...)
```

### 3.4 Threading model

| Thread | Lifetime | Purpose |
|---|---|---|
| Main | call lifetime | Validation, hook orchestration, queue polling, loop control |
| Agent stdout pump | per-iteration | Drains `agent_proc.stdout` line-by-line into `Queue` (sentinel-terminated, same pattern as Phase 2 `stream_exec`) |
| Idle watchdog | per-iteration | Dedicated thread looping `event.wait(timeout=remaining)` (see §3.6); resets on stdout activity, raises `IdleTimeout` via main-thread queue sentinel when deadline hits |
| Sandbox-hook pool | per-hook-phase | `concurrent.futures.ThreadPoolExecutor(max_workers=len(hooks))` runs sandbox hooks for one phase in parallel; pool shut down at phase end |

No threads outlive the iteration. No global thread pool. Stack traces stay readable. The model is identical in spirit to Phase 2's `stream_exec`.

### 3.5 Cancellation

`AbortSignal` wraps a `threading.Event`. Checked at:

- Every `Queue.get(timeout=0.1)` wakeup in the main loop.
- Idle-timer wakeups.
- Iteration boundaries (between iterations).
- `runner.iter_lines` exit path.

On abort: agent process gets `SIGTERM`, then `SIGKILL` after 5 s (matches Phase 2 `stream_exec` semantics). `Aborted(reason=...)` raised from `_run_loop`; teardown still runs in the `finally` block. Worktree preserved on disk if dirty (Phase 2 already provides this).

### 3.6 Idle handling

- `idle_timeout=600.0` → `IdleTimeout` raised after 600 s without stdout activity. Default per master spec.
- `idle_warning_interval=120.0` (None disables) → `StreamEvent(type="idle_warning", minutes_idle=N, ...)` emitted at 120 s, 240 s, 360 s, 480 s; the timeout still fires at 600 s.
- Implementation: single `threading.Event` per iteration. Watchdog thread loops `event.wait(timeout=remaining)`; on timeout it emits a warning event and loops; on stdout activity main thread `event.set()` then `event.clear()` to reset.

### 3.7 Completion signal

`completion_signal: str | list[str]`. Substring match (not regex) against each `line` flowing through `_run_loop`. Multi-string form: any one match ends the loop. Match recorded on `Iteration.completion_signal` and `RunResult.completion_signal`.

### 3.8 Hook execution semantics

- **Host hooks** (run on host): `subprocess.run([shell, "-c", cmd], cwd=worktree_path, env=...)` synchronous, sequential within a phase. Non-zero exit → `HookFailed`. Each host hook gets its own `Timeouts.hook_step` budget; over → `HookTimeout`.
- **Sandbox hooks** (run inside sandbox): `handle.exec(cmd, cwd=..., env=..., timeout=...)` via Phase 2 provider. Within a phase, all sandbox hooks run in parallel via `ThreadPoolExecutor`. Each hook gets a per-step timeout; aggregate failures gather into a single `HookFailed` listing all failed hooks for that phase.

```python
@dataclass(frozen=True)
class Hook:
    cmd: str
    cwd: Path | None = None                       # default: worktree_path
    env: Mapping[str, str] | None = None
    timeout: float | None = None                  # falls back to Timeouts.hook_step

@dataclass(frozen=True)
class HostHooks:
    on_worktree_ready: tuple[Hook, ...] = ()
    on_iteration_start: tuple[Hook, ...] = ()
    on_iteration_end: tuple[Hook, ...] = ()
    on_close: tuple[Hook, ...] = ()

@dataclass(frozen=True)
class SandboxHooks:
    on_sandbox_ready: tuple[Hook, ...] = ()
    on_iteration_start: tuple[Hook, ...] = ()
    on_iteration_end: tuple[Hook, ...] = ()
    on_close: tuple[Hook, ...] = ()

@dataclass(frozen=True)
class Hooks:
    host: HostHooks = HostHooks()
    sandbox: SandboxHooks = SandboxHooks()

class HookPhase(Enum):
    OnWorktreeReady = "on_worktree_ready"
    OnSandboxReady = "on_sandbox_ready"
    OnIterationStart = "on_iteration_start"
    OnIterationEnd = "on_iteration_end"
    OnClose = "on_close"
```

### 3.9 Prompt rendering

Three-stage pipeline in `eden.prompt`:

1. **Source resolution** (`_source.py`) — xor-validate `prompt`/`prompt_file`, read file if `prompt_file=` (raise `PromptError(code="prompt.file_missing")` on failure).
2. **`{{KEY}}` substitution** (`_render.py`) — apply `prompt_args` (caller supplies) plus auto-injected built-ins:
   - `{{SOURCE_BRANCH}}` — branch the agent works on (per branch strategy).
   - `{{TARGET_BRANCH}}` — host's active branch at `run()` call time.
   Unmatched `{{KEY}}` → `PromptError(code="prompt.unknown_key", hint="known keys: ...")`. Reserved-key collisions are rejected at validation step (see §2.5).
3. **`` !`cmd` `` shell-block expansion** (`_shell.py`) — regex `!`(?P<cmd>[^`]+)`` matches; each block runs via `handle.exec(cmd)` inside the sandbox; stdout substituted in place. Non-zero exit → `PromptError(code="prompt.shell_block_failed", cause=ExecFailed(...))`. Multiple blocks within one prompt run sequentially in 3a (master spec mentions parallel via `ThreadPoolExecutor`; deferred to 3b once we have a load case to justify the thread pool).

### 3.10 Env merge

`eden.env._merge.merge_env(provider_env, caller_env)`:

- No implicit override: any key set by both layers must hold the same value.
- Collision (same key, different value) → `EnvMergeError(code="config.env_merge", message="...", hint="rename one of: ...")`.
- Same key, same value → no error (idempotent).
- Disjoint keys → simple union.

Agent-level env is **not** layered in 3a (no agent has env yet). 3b adds a third tier: `merge_env(provider_env, agent_env, caller_env)` with the same collision discipline.

### 3.11 Logging (3a — file sink + redaction)

```python
@dataclass(frozen=True)
class Logging:
    type: Literal["file"]                         # 3a: file only; "stdout" added in 3b
    path: Path
    level: Literal["debug", "info", "warn", "error"] = "info"

    @staticmethod
    def file(path: str | Path, level: str = "info") -> "Logging": ...
```

- **Default when `logging` kwarg is None:** `Logging.file(".eden/logs/<sanitized-branch>-<utc>.log")`. Sanitization: replace `/`, `\\`, whitespace with `-`; truncate to 64 chars; UTC timestamp `%Y%m%dT%H%M%SZ`.
- **File format:** newline-delimited plain text. Each line: `<iso-utc> <level> [<iter>] <type>: <body>`.
- **Redaction (always on):** scans known env-var values plus prefix patterns: `sk-ant-`, `ghp_`, `xoxb-`, `xoxp-`. Matches replaced with `<redacted>`. Applied to `text` event content and shell-block stdout (which gets logged before substitution into the prompt).

## 4. Errors, results, testing

### 4.1 Exception hierarchy (3a additions)

```
EdenError                                   (Phase 2 — base)
├── ConfigError                             NEW
│   ├── InvalidOptions                      NEW   kwargs xor / type / reserved-key
│   ├── PromptError                         NEW   file missing, unreadable, !`cmd` failed in-sandbox, unknown {{KEY}}
│   ├── EnvMergeError                       NEW   caller env collides with provider env
│   └── CwdError                            NEW   cwd missing or not a git repo
├── HookError                               NEW
│   ├── HookFailed                          NEW   non-zero exit (host) or aggregated sandbox failures
│   └── HookTimeout                         NEW   hook step exceeded Timeouts.hook_step
├── EdenTimeoutError(builtins.TimeoutError) NEW   also subclasses builtin TimeoutError
│   ├── IdleTimeout                         NEW   idle_timeout elapsed
│   └── StepTimeout                         NEW   Timeouts.iteration_step elapsed mid-iteration
└── Aborted                                 NEW   AbortSignal triggered
```

(Phase 2 sandbox/worktree errors unchanged. Agent + Session errors land in 3b.)

Every new subclass carries `code: str` (stable id, e.g. `"config.invalid_options"`), `message: str`, optional `hint: str | None`, optional `cause: Exception | None`. Same shape Phase 2 already follows.

### 4.2 Result dataclasses

```python
@dataclass(frozen=True)
class RunResult:
    iterations: list[Iteration]                    # 3a: populated
    completion_signal: str | None                  # 3a: populated
    branch: str                                    # 3a: populated
    stdout: str                                    # 3a: full concatenated agent stdout
    commits: list[Commit]                          # 3a: always [] — populated in 3b
    worktree_path: Path                            # 3a: populated
    preserved_worktree_path: Path | None           # 3a: populated (from WorktreeHandle.close)
    merged_to_target_branch: str | None            # 3a: always None — populated in 3b
    cwd: Path                                      # 3a: populated
    prompt: str                                    # 3a: rendered prompt as sent to agent (post-shell-block expansion)
    env: dict[str, str]                            # 3a: merged env (caller + provider)
    log_file_path: Path | None                     # 3a: populated when Logging.file used
    session_id: str | None                         # 3a: always None — 3b
    session_file_path: Path | None                 # 3a: always None — 3b
    usage: Usage | None                            # 3a: always None — 3b

@dataclass(frozen=True)
class Iteration:
    index: int
    completion_signal: str | None
    session_id: str | None                         # 3a: None
    session_file_path: Path | None                 # 3a: None
    usage: Usage | None                            # 3a: None

@dataclass(frozen=True)
class StreamEvent:
    type: Literal["text", "idle_warning"]          # 3a: 2 types; "tool_call" added in 3b
    agent_name: str
    iteration: int
    timestamp: datetime
    text: str | None = None                        # type == "text"
    minutes_idle: int | None = None                # type == "idle_warning"

@dataclass(frozen=True)
class Usage:                                       # exported but always None in 3a; populated in 3b
    input_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int
    output_tokens: int

@dataclass(frozen=True)
class Commit:                                      # exported but list always [] in 3a
    sha: str

@dataclass(frozen=True)
class Timeouts:
    hook_step: float = 60.0
    iteration_step: float | None = None            # None disables per-iteration step timeout
```

All result types are frozen. 3b expansion is field population only — no shape changes.

### 4.3 Test strategy (Q7 hybrid)

**Unit tests** (`tests/unit/`, marker `unit`, every OS in matrix):

| Module | Coverage targets |
|---|---|
| `eden.prompt._source` | xor validation, file-missing → `PromptError`, reserved key → `InvalidOptions` |
| `eden.prompt._render` | `{{KEY}}` substitution, built-ins, missing key → `PromptError`, escaping |
| `eden.prompt._shell` | `` !`cmd` `` expansion via fake `handle.exec`, multi-block sequencing, failure → `PromptError` |
| `eden.lifecycle._runner` | host sequential, sandbox parallel, hook failure aggregation, timeout |
| `eden.orchestrator._completion` | string match, list-of-string match, no-match returns None |
| `eden.orchestrator._idle` | warning emitted at intervals, timeout raises `IdleTimeout`, activity resets |
| `eden.orchestrator._runner` | spawn, line pump, terminate on completion, SIGTERM→SIGKILL on abort |
| `eden.orchestrator._setup` | every validation rule, ordering, no side effects on failure |
| `eden.env._merge` | caller wins over provider, collision → `EnvMergeError` |
| `eden.logging._redact` | each prefix pattern, env-value, multi-match line |
| `eden.streaming._buffer` | partial-line buffering, multi-line chunks |
| `eden.abort._signal` | trigger propagates, idempotent abort |
| `eden.agents.simulated` | deterministic output, delay_per_line, fail_with |

**Smoke E2E** (`tests/e2e/`, marker `e2e`, every OS):

A single test runs `simulated_agent` + `no_sandbox` + `merge_to_head` strategy with `idle_warning_interval=0.05s`, `delay_per_line=0.1s`. Asserts:

- `RunResult.completion_signal` matches simulator output.
- `RunResult.iterations` length == 1.
- `RunResult.log_file_path` exists and contains rendered prompt + agent output.
- `RunResult.preserved_worktree_path is None` (clean worktree).
- At least one `idle_warning` event fired through `on_event`.
- Stdout contains rendered prompt args (via `{{KEY}}` substitution).

No docker E2E in 3a (deferred to 3b per Q7).

### 4.4 Coverage / type gates

- **mypy --strict** on `eden/` and `tests/` (Phase 2 gate continues; new modules must satisfy).
- **Coverage floor 70%** on `eden/` (master-spec gate).
- **ruff format + lint** clean on every push.
- **CI matrix** unchanged: Linux/macOS/Windows × py3.11/3.12/3.13. Unit + e2e markers run on every job; integration marker (Phase 2) stays Linux-only.

## 5. Risks & mitigations

| Risk | Mitigation |
|---|---|
| `threading.Event`-based idle watchdog races on activity-burst boundary. | Test exercises idle reset after 95% of `idle_timeout` elapsed; assertion on `IdleTimeout` not raised. |
| Sandbox-hook `ThreadPoolExecutor` leaks workers on phase-level exception. | Use `with ThreadPoolExecutor(...)` context manager; pool always shut down on phase exit. Test: hook raises → pool shut down → asserted via thread count post-call. |
| `simulated_agent` doesn't pressure-test the orchestrator's spawn-failure path. | `fail_with=...` knob lets tests force `subprocess.Popen` to raise; orchestrator surface tested without a real agent CLI. |
| Phase-2 worktree lock holds the file across the whole run, blocking `read_text` on Windows for stale-recovery scans. | Already fixed in Phase 2 follow-up commit (`d9aae08`); 3a inherits the phantom-lock-byte pattern unchanged. |
| `RunResult` shape divergence between 3a and 3b. | All deferred fields ship in 3a as `None` / `[]`; 3b only changes the populator, not the dataclass. CI gates the shape via mypy. |
| Hook ordering ambiguity between host and sandbox at the same phase. | Documented contract: at every phase, host runs first (sequential), then sandbox (parallel). Tested in `eden.lifecycle._runner` unit suite. |

## 6. Glossary additions (relative to master spec)

- **3a / 3b** — the two halves of master Phase 3. 3a (this spec) is orchestration core driven by simulated agents; 3b adds the first real agent (Claude) plus session capture.
- **IterationContext** — the record an `Agent.build_command(...)` receives at iteration time: iteration index, rendered prompt, the live `SandboxHandle`, worktree path, branch, optional name.
- **HookPhase** — one of `OnWorktreeReady`, `OnSandboxReady`, `OnIterationStart`, `OnIterationEnd`, `OnClose`. Drives both host and sandbox hook lists.
- **Idle warning** — periodic `StreamEvent(type="idle_warning", minutes_idle=N)` emitted while the agent has produced no stdout for at least one `idle_warning_interval`.

## Open questions

None at design time. All sections were explicitly approved before this spec was written.
