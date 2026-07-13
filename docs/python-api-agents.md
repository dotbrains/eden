# Python API: Agents and Sessions

Detailed reference for agent protocols, built-in factories, and session storage helpers. See [Python API](python-api.md) for the canonical public API index.

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
    model: str = "claude-opus-4-8",
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

`permission_mode` gives graduated tool-approval control via `--permission-mode <mode>` (`"default"`, `"acceptEdits"`, `"plan"`, `"bypassPermissions"`) — a middle ground between prompting on every tool and the all-or-nothing `dangerously_skip_permissions`. The two are mutually exclusive; passing `permission_mode` alongside `dangerously_skip_permissions=True`, or an unrecognised mode, raises `InvalidOptions(code="config.invalid_options")`. See [agents.md](agents.md#claude_code) for the per-mode semantics.

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

## Sessions

Moved to [Python API: Sessions](python-api-sessions.md).

Compatibility anchors:

<a id="session-storage"></a>
<a id="claudesessionstorage"></a>
<a id="codexsessionstorage"></a>
<a id="pisessionstorage"></a>
<a id="session-lookup-helpers"></a>
<a id="transfer_session"></a>

- [`SessionStorage`](python-api-sessions.md#session-storage)
- [`ClaudeSessionStorage`](python-api-sessions.md#claudesessionstorage)
- [`CodexSessionStorage`](python-api-sessions.md#codexsessionstorage)
- [`PiSessionStorage`](python-api-sessions.md#pisessionstorage)
- [Session lookup helpers](python-api-sessions.md#session-lookup-helpers)
- [`transfer_session`](python-api-sessions.md#transfer_session)
