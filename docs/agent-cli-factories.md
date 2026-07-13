# Agent CLI Factories

Detailed reference for Eden's `cli_agent`-backed factories and generic CLI adapter. See [Agent factories](agent-factories.md) for `simulated_agent` and `claude_code`.

## `codex`

```python
from eden import codex

agent = codex("gpt-5")
```

### Signature

```python
def codex(
    model: str = "gpt-5",
    *,
    name: str = "codex",
    effort: Literal["low", "medium", "high", "xhigh"] | None = None,
    env: Mapping[str, str] | None = None,
    capture_sessions: bool = True,
    dangerously_bypass_approvals_and_sandbox: bool = True,
    approvals_reviewer: Literal["user", "auto_review"] | None = None,
    extra_args: tuple[str, ...] = (),
) -> Agent: ...
```

Builds `codex exec [resume <id>] --json [--dangerously-bypass-approvals-and-sandbox] -m <model> [-c model_reasoning_effort="<level>"] [extra_args ...]` and delivers the prompt via stdin.

### Options

- `effort` — optional reasoning level; threads `-c model_reasoning_effort="<level>"`. One of `"low"`, `"medium"`, `"high"`, `"xhigh"`.
- `capture_sessions` — when `True` (default), the orchestrator post-processes each iteration's session JSONL into `.eden/sessions/` via [`CodexSessionStorage`](python-api.md#codexsessionstorage). Resume a captured session via the top-level `run(..., resume_session=<id>)` (requires `max_iterations=1`).
- `dangerously_bypass_approvals_and_sandbox` — when `True` (default), appends `--dangerously-bypass-approvals-and-sandbox` so codex does not block on per-tool approval prompts. Safe inside an isolated sandbox; think twice before enabling for `no_sandbox()`. Superseded by `approvals_reviewer="auto_review"`.
- `approvals_reviewer` — maps to codex's `approvals_reviewer` config key (`-c approvals_reviewer="<value>"`). When `"auto_review"`, swaps the bypass flag for an interactive approval policy plus codex's most permissive sandbox (`-a on-request -s danger-full-access`), so an AI reviewer mediates per-action approvals instead of skipping them outright — eden's sandbox provider still owns the outer filesystem boundary. `"user"` (and unset) keep the default bypass behaviour. An unrecognised value raises `InvalidOptions`.

### parse_stream

Decodes codex JSONL events: `thread.started` → `session_id`, `item.completed`/`agent_message` → `text`, `item.started`/`command_execution` → `tool_call` (Bash), `error` → `text`. Live display, file logs, and `on_agent_stream_event` callbacks see structured events instead of one-line-per-token noise.

### What binary it wraps

The `codex` CLI from OpenAI. Must be on `$PATH`. The `"gpt-5"` default is illustrative — supply whatever model identifier your installed `codex` accepts.

## `opencode`

```python
from eden import opencode

agent = opencode("claude-opus-4")
```

### Signature

```python
def opencode(
    model: str = "claude-opus-4",
    *,
    name: str = "opencode",
    variant: str | None = None,
    agent: str | None = None,
    env: Mapping[str, str] | None = None,
    dangerously_skip_permissions: bool = False,
    extra_args: tuple[str, ...] = (),
) -> Agent: ...
```

Builds the argv `opencode run --format json --model <model> [--variant <v>] [--agent <name>] [--dangerously-skip-permissions] [extra_args] <prompt>`. `--format json` is always present so the bundled stream parser receives structured events; without it, opencode would emit free-form text and the orchestrator's per-line fallback would silently drop session ids and tool calls.

`captures_sessions` is `False` (no `OpenCodeSessionStorage` ships today; the parser does surface `step_start` events so `Iteration.session_id` populates).

### Options

- `variant` — reasoning-effort variant passed via `--variant` (e.g. `"high"`, `"max"`, `"low"`, `"minimal"`); omit to keep opencode's default.
- `agent` — named agent mode passed via `--agent` (e.g. `"build"` / `"plan"`); selects a different built-in opencode persona per mode.
- `dangerously_skip_permissions` — when `True`, appends `--dangerously-skip-permissions` so opencode does not block on per-tool permission prompts. Safe inside isolated sandboxes; think twice before enabling for `no_sandbox()`. Default `False`.

### parse_stream

Decodes opencode JSONL events: `step_start` → `session_id`, `text`/`part.type==text` → `text`, `tool_use`/`part.type==tool` (only on `state.status=="completed"`) → `tool_call`, `error` → `text`.

### What binary it wraps

The `opencode` CLI from `sst/opencode`. Must be on `$PATH`. opencode supports multiple model providers; the default `model="claude-opus-4"` is illustrative — pass whatever identifier opencode expects.

## `pi`

```python
from eden import pi

agent = pi("pi-3.5")
```

### Signature

```python
def pi(
    model: str = "pi-3.5",
    *,
    env: Mapping[str, str] | None = None,
    extra_args: tuple[str, ...] = (),
) -> Agent: ...
```

Thin wrapper over [`cli_agent`](#cli_agent) with `binary="pi"` and `name="pi"`. `captures_sessions` is `False`. Wires a `parse_stream` that decodes pi JSONL events (`message_update`/`text_delta` → `text`, `tool_execution_start` → `tool_call` for known tools (Bash, WebSearch, WebFetch, Agent), `agent_end` → final-message `text`, `agent_error`/`error` → `text`) so live display and file logs see structured events instead of one-line-per-token noise.

### What binary it wraps

The `pi` CLI from Inflection. Must be on `$PATH`.

## `cursor`

Moved to [Agent CLI editor factories](agent-cli-editor-factories.md#cursor).

Compatibility anchors: <a id="cursor"></a>

## `copilot`

Moved to [Agent CLI editor factories](agent-cli-editor-factories.md#copilot).

Compatibility anchors: <a id="copilot"></a>

## `cli_agent`

Moved to [Agent CLI adapter](agent-cli-adapter.md#cli_agent).

Compatibility anchors: <a id="cli_agent"></a>

## See also

- [Agent factories](agent-factories.md) — `simulated_agent` and `claude_code`.
- [Agent CLI editor factories](agent-cli-editor-factories.md) — `cursor` and `copilot`.
- [Agent CLI adapter](agent-cli-adapter.md) — generic `cli_agent` reference.
- [Agents](agents.md) — factory matrix, Flox runtimes, and authentication.
- [Python API: Agents](python-api-agents.md) — public Protocol and session helper reference.
