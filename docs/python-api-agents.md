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

Built-in factories return an `Agent`. Use this page for the public Protocol and
context types; use the dedicated factory references for signatures and CLI
details.

Every CLI-backed factory (`claude_code`, `codex`, `opencode`, `pi`, `cursor`,
`copilot`, `cli_agent`) accepts `flox_env: str | Path | None = None`. When set,
Eden runs that agent's CLI via `flox activate -d <dir> -- <argv>`. A missing
manifest or `flox` binary raises [`FloxEnvError`](#errors); set
`EDEN_ALLOW_NO_FLOX=1` to skip activation where Flox is unavailable. See
[Agent Flox runtime](agent-flox-runtime.md) and ADR-0014.

#### `simulated_agent(...)`

Moved to [Agent factories](agent-factories.md#simulated_agent).

#### `claude_code(...)`

Moved to [Claude Code agent](agent-claude-code.md#claude_code).

#### `codex(...)`

Moved to [Agent CLI factories](agent-cli-factories.md#codex).

#### `opencode(...)`

Moved to [Agent CLI other factories](agent-cli-other-factories.md#opencode).

#### `pi(...)`

Moved to [Agent CLI other factories](agent-cli-other-factories.md#pi).

#### `cursor(...)`

Moved to [Agent CLI editor factories](agent-cli-editor-factories.md#cursor).

#### `copilot(...)`

Moved to [Agent CLI editor factories](agent-cli-editor-factories.md#copilot).

#### `cli_agent(...)`

Moved to [Agent CLI adapter](agent-cli-adapter.md#cli_agent).

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
