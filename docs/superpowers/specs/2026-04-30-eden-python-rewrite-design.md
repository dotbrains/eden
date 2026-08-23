# Eden — Python rewrite design

**Date:** 2026-04-30
**Status:** Approved (brainstorming → spec)
**Outcome:** Greenfield Python 3 rewrite; the existing Rust workspace is deleted with no migration path.

## Context

Eden today is a Rust workspace (~14k LoC across 5 crates) that orchestrates AI coding agents in sandboxed git worktrees. The user-facing API (`RunOptions`, `InteractiveOptions`, `BindMountProvider`, `BranchStrategy`, etc.) has accreted Rust-shaped abstractions (`PipelineOptions<Body>::split()`, `SessionSetup`, `WithCloseResult`, `SandboxHandleKind::{Direct, Finalizing}`) that exist primarily to satisfy the borrow checker and trait-object dispatch.

The benchmark for "as simple as possible" is a programmatic API that boils down to a single `run({ agent, sandbox, promptFile })` call plus an `init` command for scaffolding.

The directory `/Users/nicholas/Documents/GitHub/github.com/smeltery/eden` exists but is **not yet a git repo**, and Eden has **no users**. The rewrite is therefore unconstrained by API stability or migration concerns.

## Goals

- A public API as terse as that single-call benchmark, but written for Python 3.
- Full feature parity with current Rust Eden: docker / podman / vercel / daytona / isolated / no-sandbox providers; claude-code / codex / opencode / pi agents; iteration loop with completion signal; idle timeout + warnings; `{{KEY}}` prompt args; `` !`cmd` `` shell blocks; lifecycle hooks; three branch strategies; resume sessions; streaming agent events; file logging; token usage aggregation; interactive (TTY) mode.
- YAGNI applied to **internal abstractions** (drop Rust-isms) but **not** to user-facing features.
- Sync-first public API. No `asyncio` in v1.
- Single PyPI distributable: `pip install eden-agent`. No native compilation.

## Non-goals

- No async (`arun`) variant in v1. Add later if a real embedder use case surfaces.
- No backwards compatibility with the Rust API. The Rust code is deleted.
- No migration guide. There are no users to migrate.
- No telemetry, GUI, web dashboard, project-level `eden.toml`, `eden upgrade`/`self-update`.
- No public API stability guarantee until v1.0.0.

## Decisions

| # | Decision | Rationale |
|---|---|---|
| 1 | **Language: Python 3.11+** | Terser than Rust; the AI-engineer audience lives here; native sync subprocess avoids the language-tax that forces JS/TS orchestrators to be async. |
| 2 | **Drop Rust crates entirely** | Greenfield rewrite. No users to break. |
| 3 | **Approach 2: Python-idiomatic re-architecture** | Keep behaviors, redesign the *shape* using dataclasses, `Protocol`, context managers, generators. Approach 1 (1:1 port) carries Rust-isms that cost without paying. Approach 3 (lean on `claude-code-sdk`) limits parity with non-Claude agents. |
| 4 | **Sub-namespaced package** (`eden.sandboxes.docker`, `eden.providers.*`) | A clean, discoverable import shape. Single PyPI package; namespace is curated re-exports, not multi-package monorepo. |
| 5 | **Sync-first API** (`run(...)` blocks) | JS/TS orchestrators are async only because the language forces it. Python can offer real sync. The default audience is script-style users; embedders can `asyncio.to_thread(run, ...)` until/unless `arun` is added. |

## Section 1 — Public API surface

### Quick start

```bash
pip install eden-agent
eden init
cp .eden/.env.example .eden/.env
python .eden/main.py
```

### Default `main.py`

```python
from eden import run, claude_code
from eden.sandboxes import docker

run(
    agent=claude_code("claude-opus-4-6"),
    sandbox=docker(),
    prompt_file=".eden/prompt.md",
)
```

### Top-level package — `eden`

| Export | Purpose |
|---|---|
| `run(...)` | Non-interactive iteration loop; returns `RunResult`. Sync. |
| `interactive(...)` | TTY-attached agent invocation; returns `InteractiveResult`. Sync. |
| `create_sandbox(...)` | Reusable sandbox (multi-run); returns a `Sandbox` context manager. |
| `create_worktree(...)` | Worktree without a sandbox; returns a `Worktree` context manager. |
| `claude_code(model, *, effort=None, env=None, capture_sessions=True)` | Agent factory. |
| `codex(model, *, effort=None, env=None)` | Agent factory. |
| `opencode(model, *, env=None)` | Agent factory. |
| `pi(model, *, env=None)` | Agent factory. |
| `BranchStrategy` | `.head()` / `.merge_to_head()` / `.named(branch, base="main")`. |
| `Hook`, `Hooks`, `HostHooks`, `SandboxHooks` | Lifecycle hook config. |
| `Logging`, `Timeouts`, `Mount`, `Usage`, `Commit`, `Iteration`, `RunResult`, `InteractiveResult`, `CloseResult`, `StreamEvent` | Result + config dataclasses. |
| `AbortController`, `AbortSignal` | Cancellation. |
| `EdenError` and subclasses | Exception hierarchy. |

### Sub-namespace — `eden.sandboxes`

| Export | Purpose |
|---|---|
| `docker(image=None, mounts=None, env=None, network=None)` | Docker bind-mount provider. |
| `podman(image=None, mounts=None, env=None, network=None)` | Podman bind-mount provider. |
| `vercel(...)` | Vercel cloud (isolated, finalizing). |
| `daytona(...)` | Daytona cloud (isolated, finalizing). |
| `isolated(...)` | Local temp-dir worktree with patch-sync. |
| `no_sandbox()` | Run on host (interactive only). |

### Sub-namespace — `eden.providers`

For users authoring custom sandbox providers.

| Export | Purpose |
|---|---|
| `make_bind_mount_provider(name, create)` | Factory helper for bind-mount providers. |
| `make_isolated_provider(name, create)` | Factory helper for isolated providers. |
| `SandboxProvider` (Protocol) | Provider interface. |
| `SandboxHandle`, `BindMountSandboxHandle`, `IsolatedSandboxHandle` (Protocols) | Handle interfaces. |
| `ExecResult` | `{stdout, stderr, exit_code}` dataclass. |
| `MountConfig` | Mount configuration dataclass. |

### `run(...)` full signature

```python
def run(
    *,
    agent: Agent,
    sandbox: SandboxProvider,
    prompt: str | None = None,
    prompt_file: str | Path | None = None,            # exactly one of prompt/prompt_file
    prompt_args: dict[str, str] | None = None,
    cwd: str | Path | None = None,
    env: dict[str, str] | None = None,
    branch_strategy: BranchStrategy | None = None,    # auto-picked per provider tag
    max_iterations: int = 1,
    completion_signal: str | list[str] = "<promise>COMPLETE</promise>",
    idle_timeout: float | timedelta = 600.0,
    idle_warning_interval: float | timedelta | None = None,
    name: str | None = None,
    hooks: Hooks | None = None,
    copy_to_worktree: list[str] | None = None,
    timeouts: Timeouts | None = None,
    resume_session: str | None = None,
    on_event: Callable[[StreamEvent], None] | None = None,
    logging: Logging | None = None,                   # default: file under .eden/logs/
    signal: AbortSignal | None = None,
) -> RunResult: ...
```

**Validation rules (raise `InvalidOptions`):**

- Exactly one of `prompt` / `prompt_file` must be provided.
- `prompt_args` is only valid with `prompt_file`.
- `prompt_args` must not contain reserved keys `SOURCE_BRANCH` or `TARGET_BRANCH`.
- `branch_strategy` (if explicit) must be supported by the provider's tag.
- `resume_session` requires `max_iterations == 1` and an agent that supports resume.
- Agent-level `env` and sandbox-level `env` must not share any key.

### Built-in prompt args (auto-injected into file prompts)

| Placeholder | Value |
|---|---|
| `{{SOURCE_BRANCH}}` | The branch the agent works on (per branch strategy). |
| `{{TARGET_BRANCH}}` | The host's active branch at `run()` time. |

### `create_sandbox(...)` — reusable sandbox

```python
with create_sandbox(branch="agent/fix-42", sandbox=docker()) as sb:
    sb.run(agent=claude_code("claude-opus-4-6"), prompt_file=".eden/implement.md", max_iterations=5)
    sb.run(agent=claude_code("claude-sonnet-4-6"), prompt="Review and fix issues.")
# auto-close on context exit; container torn down; worktree preserved if dirty.
```

`Sandbox` exposes: `branch`, `worktree_path`, `run(...)`, `interactive(...)`, `close() -> CloseResult`.

### `create_worktree(...)` — worktree without sandbox

```python
with create_worktree(branch_strategy=BranchStrategy.named("agent/fix-42")) as wt:
    wt.interactive(agent=claude_code("..."), prompt="Explore.")           # default: no_sandbox()
    wt.run(agent=claude_code("..."), sandbox=docker(), prompt="Fix it.")  # sandbox required
    with wt.create_sandbox(sandbox=docker()) as sb:
        sb.run(...)
```

`Worktree` exposes: `branch`, `worktree_path`, `run(...)`, `interactive(...)`, `create_sandbox(...)`, `close() -> CloseResult`.

`wt.close()` cleans up the worktree only; sandboxes created via `wt.create_sandbox()` tear down their container but leave the worktree alone (split ownership).

### Custom provider authoring

```python
from eden.providers import make_bind_mount_provider, ExecResult

def local_process():
    def create(opts):
        wt = opts.worktree_path
        def exec_(cmd, *, on_line=None, cwd=None) -> ExecResult: ...
        def copy_file_in(host, sb): ...
        def copy_file_out(sb, host): ...
        def close(): ...
        return BindMountHandle(worktree_path=wt, exec=exec_, ...)
    return make_bind_mount_provider(name="local-process", create=create)
```

### Excluded from public API

- `PipelineOptions`, `SessionSetup`, `SandboxRunOptions`, `SandboxHandleKind`, `WithCloseResult`, `RunOutputAggregates`.
- `IterationRunner`, `RealAgentRunner`, `SimulatedAgentRunner` as exports. Simulated mode survives as `EDEN_AGENT_EXEC_MODE=simulated` env var.
- Agent introspection helpers (`agent_descriptor`, `supported_agent_names`).

## Section 2 — Internal architecture

### Package tree

```
eden/
├── __init__.py                  # curated public re-exports (~20 names)
├── _version.py
├── agents/
│   ├── __init__.py              # claude_code, codex, opencode, pi factories
│   ├── base.py                  # Agent Protocol + StreamEventKind
│   ├── claude_code.py
│   ├── codex.py
│   ├── opencode.py
│   ├── pi.py
│   └── parse.py
├── sandboxes/
│   ├── __init__.py              # (intentionally empty)
│   ├── docker.py
│   ├── podman.py
│   ├── vercel.py
│   ├── daytona.py
│   ├── isolated.py
│   └── no_sandbox.py
├── providers/
│   ├── __init__.py              # public custom-provider authoring kit
│   └── _impl/
│       ├── container.py         # docker/podman common
│       ├── http_rest.py         # cloud REST helpers
│       ├── patch_sync.py        # 4-phase isolated finalization
│       ├── path_resolve.py
│       └── redact.py
├── orchestrator/
│   ├── __init__.py
│   ├── loop.py                  # iterate()
│   ├── completion.py            # completion-signal matcher
│   ├── idle.py                  # idle timeout + warning emitter
│   └── runner.py                # Real / Simulated runners
├── prompt/
│   ├── __init__.py
│   ├── source.py                # PromptSource = Inline | File
│   ├── render.py                # {{KEY}} substitution + built-ins
│   └── shell.py                 # !`cmd` expansion (in-sandbox)
├── worktree/
│   ├── __init__.py
│   ├── handle.py
│   ├── lock.py                  # .eden/worktrees/<name>.lock RAII
│   └── strategy.py              # BranchStrategy
├── session/
│   ├── __init__.py
│   ├── store.py                 # Claude session JSONL capture + cwd rewrite
│   └── encode.py
├── lifecycle/
│   ├── __init__.py
│   ├── phases.py
│   └── runner.py                # sequential host hooks; parallel sandbox hooks
├── pipeline/
│   ├── __init__.py
│   └── setup.py                 # internal: cwd resolve, env merge, prompt resolve, finalize
├── env/
│   ├── __init__.py
│   └── loader.py                # .eden/.env loader + layered merge
├── logging/
│   ├── __init__.py
│   ├── config.py                # Logging dataclass + factories
│   ├── stdout.py                # rich-rendered TTY UI
│   ├── file.py                  # plain-text sink
│   └── format.py
├── streaming/
│   ├── __init__.py
│   └── buffer.py                # TextDeltaBuffer
├── abort/
│   ├── __init__.py
│   └── signal.py                # AbortController / AbortSignal
├── errors/
│   ├── __init__.py
│   └── hints.py
├── cli/
│   ├── __init__.py
│   ├── main.py                  # typer app
│   ├── init.py                  # `eden init`
│   ├── run.py                   # `eden run` ad-hoc wrapper
│   ├── docker.py                # `eden docker build-image|remove-image`
│   ├── podman.py
│   └── templates/
│       ├── blank/
│       ├── simple-loop/
│       ├── sequential-reviewer/
│       ├── parallel-planner/
│       └── parallel-planner-with-review/
├── _types.py                    # tiny shared dataclasses: Usage, Commit, Mount, Timeouts, Logging
└── py.typed                     # PEP 561 marker
```

### Core protocols

```python
# eden/agents/base.py
@runtime_checkable
class Agent(Protocol):
    name: str
    model: str
    def build_command(self, ctx: IterationContext) -> list[str]: ...
    def parse_stream(self, line: str) -> StreamEvent | None: ...
    def supports_resume(self) -> bool: ...
    def supports_session_capture(self) -> bool: ...

# eden/providers/__init__.py
@runtime_checkable
class SandboxProvider(Protocol):
    name: str
    kind: ProviderKind                        # "bind_mount" | "isolated" | "none"
    def create(self, opts: CreateOptions) -> SandboxHandle: ...
    def supports_strategy(self, s: BranchStrategy) -> bool: ...

@runtime_checkable
class SandboxHandle(Protocol):
    worktree_path: Path
    def exec(self, cmd: str, *, on_line=None, cwd=None) -> ExecResult: ...
    def copy_file_in(self, host: Path, sb: Path) -> None: ...
    def copy_file_out(self, sb: Path, host: Path) -> None: ...
    def close(self) -> None: ...
    # isolated handles additionally implement:
    def finalize(self, target: Path) -> FinalizeResult: ...   # optional
```

`SandboxHandleKind::Direct/Finalizing` in Rust collapses to: a handle has `finalize()` or it doesn't. Orchestrator uses `hasattr(handle, "finalize")` once at close time. No enum, no boxed dispatch.

### Concurrency model

- **Sync top-level API.** `run(...)` blocks the caller's thread.
- **Internal threading where it pays off.** Lifecycle hooks marked "parallel" via `concurrent.futures.ThreadPoolExecutor`. Multiple `` !`cmd` `` blocks in a prompt run in parallel through the same executor. Per-iteration agent stdout pumps on a background thread into the on-event callback and idle-timer.
- **No `asyncio` anywhere.** Blocking I/O + threads. Keeps stack traces readable.

### Test-mode toggle

`EDEN_AGENT_EXEC_MODE=simulated` swaps `RealAgentRunner` for `SimulatedAgentRunner` (deterministic output, no subprocess). Not in public API.

### Module size budget

~300 LoC ceiling per `.py` file. Larger modules get split.

### Dropped from the Rust shape

- `PipelineOptions<Body>` generic + `split()`
- `SessionSetup`
- `WithCloseResult` trait
- `RunOutputAggregates`
- `SandboxHandleKind::Direct/Finalizing` enum
- `with_pipeline_setup(...)`
- `AgentRunnerSelection::{Auto, Real, Simulated, Custom(Box<dyn>)}`

## Section 3 — Init flow, CLI, and on-disk layout

### `eden init`

Interactive scaffolder that asks for sandbox provider, backlog manager, agent, model, and template, then writes `.eden/`. Non-interactive flags for CI:

| Flag | Default | Notes |
|---|---|---|
| `--sandbox docker\|podman` | interactive prompt | |
| `--agent claude-code\|codex\|opencode\|pi` | interactive prompt | |
| `--model <str>` | agent's default | |
| `--template <name>` | interactive prompt | One of the 5 templates. |
| `--image-name <name>` | `eden:<repo-dir-name>` | |
| `--yes` | — | Accept all defaults. |

`init` refuses to overwrite an existing `.eden/`. No `--force` flag in v1.

### `.eden/` directory

```
.eden/
├── Dockerfile           # or Containerfile for podman
├── prompt.md
├── main.py
├── .env.example
├── .gitignore
├── logs/                # auto-created
└── worktrees/           # auto-created
```

### Default `main.py` (blank template)

```python
from eden import run, claude_code
from eden.sandboxes import docker

if __name__ == "__main__":
    run(
        agent=claude_code("claude-opus-4-6"),
        sandbox=docker(),
        prompt_file=".eden/prompt.md",
    )
```

### Templates

| Template | What it scaffolds |
|---|---|
| `blank` | Bare prompt + 7-line `main.py`. |
| `simple-loop` | Picks GitHub issues with label `eden`, closes them one by one. |
| `sequential-reviewer` | Implement → review-and-fix loop using two `claude_code` calls inside one `create_sandbox(...)` block. |
| `parallel-planner` | Plans parallelizable issues, fans out to one branch per issue, then merges. |
| `parallel-planner-with-review` | `parallel-planner` + per-branch review step before merge. |

Each template's `main.py` is hand-written Python — no codegen.

### `eden` CLI commands

| Command | Purpose |
|---|---|
| `eden init` | Scaffold `.eden/`. |
| `eden run [...]` | Convenience wrapper around `run()`. |
| `eden interactive [...]` | Convenience wrapper around `interactive()`. |
| `eden docker build-image [--image-name <name>] [--dockerfile <path>]` | Build the sandbox image. |
| `eden docker remove-image [--image-name <name>]` | Remove the image. |
| `eden podman build-image [...]` | Same for podman. |
| `eden podman remove-image [...]` | |
| `eden version` | Print version. |
| `eden --help` / `eden <cmd> --help` | Help. |

CLI built on `typer` + `rich`. No `eden new`, `eden config`, `eden doctor`, `eden upgrade` in v1.

### Packaging

```toml
[project]
name = "eden-agent"
requires-python = ">=3.11"
dependencies = [
    "typer >= 0.12",
    "rich >= 13.7",
    "questionary >= 2.0",
    "python-dotenv >= 1.0",
    "anyio >= 4.4",
]

[project.optional-dependencies]
vercel  = ["requests >= 2.32"]
daytona = ["requests >= 2.32"]

[project.scripts]
eden = "eden.cli.main:app"

[project.entry-points."eden.agents"]
claude-code = "eden.agents.claude_code:ClaudeCodeAgent"
codex       = "eden.agents.codex:CodexAgent"
opencode    = "eden.agents.opencode:OpencodeAgent"
pi          = "eden.agents.pi:PiAgent"

[project.entry-points."eden.sandboxes"]
docker     = "eden.sandboxes.docker:provider"
podman     = "eden.sandboxes.podman:provider"
vercel     = "eden.sandboxes.vercel:provider"
daytona    = "eden.sandboxes.daytona:provider"
isolated   = "eden.sandboxes.isolated:provider"
no-sandbox = "eden.sandboxes.no_sandbox:provider"
```

Entry points let third-party packages (`eden-sandbox-modal`, `eden-agent-aider`) auto-register without core changes. Cloud providers are gated by extras to keep base install lean.

## Section 4 — Errors, validation, observability

### Exception hierarchy

```
EdenError
├── ConfigError
│   ├── InvalidOptions
│   ├── CwdError
│   ├── PromptError
│   └── EnvMergeError
├── SandboxError
│   ├── ImageNotFound
│   ├── ContainerStartFailed
│   ├── ExecFailed
│   ├── CopyFailed
│   ├── UnsupportedBranchStrategy
│   ├── PatchSyncFailed
│   └── CloudProviderError
├── WorktreeError
│   ├── WorktreeLocked
│   ├── DirtyHostBlocked
│   └── MergeConflict
├── AgentError
│   ├── AgentNotFound
│   ├── AgentSpawnFailed
│   ├── AgentParseError
│   └── ResumeNotSupported
├── SessionError
│   ├── SessionFileMissing
│   └── SessionCaptureFailed
├── HookError
│   ├── HookFailed
│   └── HookTimeout
├── TimeoutError                          # also subclass of builtins.TimeoutError
│   ├── IdleTimeout
│   └── StepTimeout
└── Aborted
```

### Exception payload

```python
class EdenError(Exception):
    code: str             # stable id, e.g. "sandbox.image_not_found"
    message: str
    hint: str | None      # actionable next step
    cause: Exception | None
```

`hint` carries the recovery message inline (replaces Rust's `recovery_hint()` match). Code is the wire-stable identifier for log scraping and programmatic dispatch.

### Validation order

All input validation is synchronous and runs before any side effect (no worktree, no container, no log file until validation passes):

1. kwargs (mutual exclusivity, type checks).
2. cwd existence + git repo check.
3. Prompt source resolution (xor; readability; built-in args present).
4. Provider compatibility (branch strategy supported by provider tag).
5. Resume session preconditions.
6. Env-merge collision.

### Logging

```python
@dataclass(frozen=True)
class Logging:
    type: Literal["stdout", "file"]
    path: Path | None = None
    level: Literal["debug", "info", "warn", "error"] = "info"

    @staticmethod
    def stdout(level: str = "info") -> "Logging": ...
    @staticmethod
    def file(path: str | Path, level: str = "info") -> "Logging": ...
```

- Default: `Logging.file(".eden/logs/<sanitized-branch>-<utc>.log")`.
- Stdout mode: `rich`-rendered TUI when `sys.stdout.isatty()`; plain text otherwise.
- File mode: plain newline-delimited; tail-friendly.
- Secret redaction always on; matches known env-var values + prefix patterns (`sk-ant-`, `ghp_`, `xoxb-`).

### Streaming events

```python
@dataclass(frozen=True)
class StreamEvent:
    type: Literal["text", "tool_call", "idle_warning"]
    agent_name: str
    iteration: int
    timestamp: datetime
    text: str | None = None                  # type == "text"
    tool_name: str | None = None             # type == "tool_call"
    tool_args_formatted: str | None = None   # type == "tool_call"
    minutes_idle: int | None = None          # type == "idle_warning"
```

Errors raised inside `on_event` are caught and logged at warn level; broken forwarders never kill the run.

### Cancellation

```python
ctrl = AbortController()
ctrl.abort(reason="user pressed ctrl-c")
run(..., signal=ctrl.signal)   # raises Aborted(reason=...) when triggered
```

`AbortSignal` wraps a `threading.Event`; checked at iteration boundaries, idle-timer wakeups, subprocess `poll()` loops. On abort, in-flight agent gets `SIGTERM` then `SIGKILL` after 5 s. Worktree preserved on disk if dirty.

### Result dataclasses

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

@dataclass(frozen=True)
class InteractiveResult:
    branch: str
    worktree_path: Path
    preserved_worktree_path: Path | None
    merged_to_target_branch: str | None
    cwd: Path
    log_file_path: Path | None

@dataclass(frozen=True)
class Iteration:
    index: int
    completion_signal: str | None
    session_id: str | None
    session_file_path: Path | None
    usage: Usage | None

@dataclass(frozen=True)
class Usage:
    input_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int
    output_tokens: int

@dataclass(frozen=True)
class Commit:
    sha: str

@dataclass(frozen=True)
class CloseResult:
    preserved_worktree_path: Path | None
```

All result types are frozen dataclasses — values, not objects.

### Excluded

- No metrics/OTEL exporter (route through `on_event`).
- No structured-log JSON option in v1.
- No per-error-code message catalog file.
- No non-fatal warning channel (use exceptions or `on_event`).

## Section 5 — Build plan

### Day 0 — Initialize repo

```bash
cd /Users/nicholas/Documents/GitHub/github.com/smeltery/eden
rm -rf crates/ scripts/
rm -f  Cargo.toml Cargo.lock CONTEXT.md README.md
# Wipe Rust-flavored docs but preserve docs/superpowers/ (working specs / this file).
find docs -mindepth 1 -maxdepth 1 ! -name superpowers -exec rm -rf {} +
# (keep LICENSE)

git init -b main
git add LICENSE docs/superpowers
git commit -m "chore: initial commit (PolyForm Shield 1.0.0)"

gh repo create smeltery/eden --public --source=. --remote=origin --push
# OR: git remote add origin git@github.com:smeltery/eden.git && git push -u origin main
```

No Rust history is preserved; the directory was never a git repo. `docs/superpowers/` is preserved because it holds this design spec and any future planning artifacts.

### Phases

| Phase | Scope | Approx. effort |
|---|---|---|
| 1 — Skeleton | `git init`, `pyproject.toml`, package skeleton, `py.typed`, CI matrix (3.11/3.12/3.13 × macOS/Linux/Windows), README placeholder, `.gitignore`. Branch protection on `main` before phase 2. | 1 week |
| 2 — Sandbox foundations | `eden.providers` (Protocols, helpers, `ExecResult`), `eden.sandboxes.no_sandbox`, `eden.sandboxes.docker` MVP, `eden.worktree` (handle, lock, three branch strategies). Unit + integration tests. | 2 weeks |
| 3 — Orchestration & Claude agent | `eden.orchestrator`, `eden.prompt` (file source, args, shell blocks, built-ins), `eden.session.store`, `eden.lifecycle`, `eden.agents.claude_code`, public `run` / `interactive` / `create_sandbox` / `create_worktree`. End-to-end tests on docker + no-sandbox. | 3 weeks |
| 4 — Provider parity | `eden.sandboxes.podman`, `eden.sandboxes.isolated`, `eden.sandboxes.vercel`, `eden.sandboxes.daytona`. Cross-provider integration tests. | 2 weeks |
| 5 — Agent parity | `eden.agents.codex`, `eden.agents.opencode`, `eden.agents.pi`. Per-agent integration tests. | 1 week |
| 6 — CLI & templates | `eden init` interactive, all 5 templates, `eden run`/`interactive`/`docker`/`podman` subcommands. | 1 week |
| 7 — Docs & release | Rebuild `docs/` from scratch (see structure below), rewrite `README.md`, tag `v0.1.0`, publish `eden-agent` to PyPI. | 1 week |

**Total: ~11 weeks single contributor.** Phases 4 and 5 parallelizable.

### Repo metadata to set in phase 1

| Item | Value |
|---|---|
| Description | Python orchestrator for AI coding agents in sandboxed worktrees. |
| Topics | `agents`, `claude-code`, `codex`, `docker`, `podman`, `sandbox`, `worktree`, `python` |
| License | PolyForm Shield 1.0.0 |
| Default branch | `main` |
| Branch protection on `main` | Require PR; require CI green; no force-push. |
| Issue / PR templates | `.github/ISSUE_TEMPLATE/{bug.md, feature.md}`, `.github/PULL_REQUEST_TEMPLATE.md` |
| `CODEOWNERS` | `* @smeltery/maintainers` |
| Actions secrets | `PYPI_API_TOKEN` (added in phase 7). |

### `docs/` structure (rebuilt in phase 7)

```
docs/
├── README.md                  # table of contents
├── what-is-eden.md
├── quick-start.md
├── python-api.md              # full reference for run / interactive / create_sandbox / create_worktree
├── how-it-works.md            # branch strategies, worktrees, sandbox lifecycle, iteration loop
├── prompts.md                 # PromptSource, args, shell blocks, built-ins
├── templates.md               # 5 init templates
├── cli.md
├── configuration.md
├── sandbox-providers.md
├── agents.md
├── custom-providers.md
├── errors.md
├── development.md
└── adr/
    ├── 0001-finalizing-vs-direct-handles.md
    ├── 0002-sync-first-public-api.md
    └── 0003-one-agent-per-file.md
```

ADRs are written from scratch for this Python design; nothing carries forward from the Rust code.

### Test strategy

- pytest with markers: `unit`, `integration`, `smoke`.
- Coverage floor: 70% on `eden/` (CI gate).
- mypy strict on `eden/` (CI gate).
- Integration tests use real Docker / Podman in CI runners; skipped elsewhere with reason strings.
- Simulated mode (`EDEN_AGENT_EXEC_MODE=simulated`) for orchestrator tests without a real agent CLI.

### Risks

| Risk | Mitigation |
|---|---|
| Patch-sync (isolated provider) is intricate to design from scratch. | Ship correct-but-slow first in phase 4; optimize once tests pass. |
| Windows subprocess/signal quirks. | Run Windows in CI from phase 1; raise clear errors with hints where Unix-only behavior doesn't translate. |
| PyPI name `eden-agent` may be taken. | Reserve before phase 1. Backups: `eden-orchestrator`, `smeltery-eden`. |
| Performance regression vs Rust. | Subprocess startup dominates wall time; Python overhead is noise. Phase 7 micro-benchmark documents the tradeoff. |

### Out of scope for v1

- No async (`arun`).
- No GUI / web dashboard.
- No project-level `eden.toml` config.
- No telemetry, auto-update.
- No public API stability guarantee until v1.0.0.

## Open questions

None at design time. All five sections were explicitly approved before this spec was written.

## Glossary

- **Agent** — concrete coding-agent CLI integration (`claude-code`, `codex`, `opencode`, `pi`).
- **Sandbox provider** — execution environment factory (`docker`, `podman`, `vercel`, `daytona`, `isolated`, `no_sandbox`).
- **Sandbox handle** — runtime object returned by a provider; exposes `exec`, `copy_*`, `close`, optionally `finalize`.
- **Worktree** — git worktree carved from the host repo for one Eden run.
- **Branch strategy** — `head` (write directly to host), `merge_to_head` (temp branch, fast-forward back), `named` (explicit branch).
- **Iteration** — one agent invocation inside the orchestrator's loop.
- **Completion signal** — substring(s) the agent emits to end the loop early.
- **Lifecycle hook** — host or sandbox shell command run at a specific phase (`OnWorktreeReady`, `OnSandboxReady`).
- **Resume session** — re-enter a prior Claude Code conversation by id.
