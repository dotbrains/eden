# Agent CLI Factories

Detailed reference for Eden's `cli_agent`-backed factories and generic CLI adapter. See [Agent factories](agent-factories.md) for `simulated_agent` and `claude_code`.

---

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

Builds the invocation `codex exec [resume <id>] --json [--dangerously-bypass-approvals-and-sandbox] -m <model> [-c model_reasoning_effort="<level>"] [extra_args ...]` and delivers the prompt via stdin.

### Options

- `effort` — optional reasoning-effort level. When set, threads `-c model_reasoning_effort="<level>"` into the invocation. One of `"low"`, `"medium"`, `"high"`, `"xhigh"`.
- `capture_sessions` — when `True` (default), the orchestrator post-processes each iteration's session JSONL into `.eden/sessions/` via [`CodexSessionStorage`](python-api.md#codexsessionstorage). Resume a captured session via the top-level `run(..., resume_session=<id>)` (requires `max_iterations=1`).
- `dangerously_bypass_approvals_and_sandbox` — when `True` (default), appends `--dangerously-bypass-approvals-and-sandbox` so codex does not block on per-tool approval prompts. Safe inside an isolated sandbox; think twice before enabling for `no_sandbox()`. Superseded by `approvals_reviewer="auto_review"`.
- `approvals_reviewer` — maps to codex's `approvals_reviewer` config key (`-c approvals_reviewer="<value>"`). When `"auto_review"`, swaps the bypass flag for an interactive approval policy plus codex's most permissive sandbox (`-a on-request -s danger-full-access`), so an AI reviewer mediates per-action approvals instead of skipping them outright — eden's sandbox provider still owns the outer filesystem boundary. `"user"` (and unset) keep the default bypass behaviour. An unrecognised value raises `InvalidOptions`.

### parse_stream

Decodes codex JSONL events: `thread.started` → `session_id`, `item.completed`/`agent_message` → `text`, `item.started`/`command_execution` → `tool_call` (Bash), `error` → `text`. Live display, file logs, and `on_agent_stream_event` callbacks see structured events instead of one-line-per-token noise.

### What binary it wraps

The `codex` CLI from OpenAI. Must be on `$PATH`. The `"gpt-5"` default is illustrative — supply whatever model identifier your installed `codex` accepts.

### When to use

- Codex-driven workflows with or without session capture/resume.

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

### When to use

- Multi-provider routing workflows (opencode lets you swap LLM backends without changing the calling code).

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

### When to use

- pi-backed workflows.

## `cursor`

```python
from eden import cursor

agent = cursor("claude-sonnet-4-6")
```

### Signature

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

Builds `agent --print --output-format stream-json --model <model> [--force] [extra_args ...] <prompt>`. Cursor's CLI binary is named `agent` (not `cursor`); make sure it's on `$PATH`. The prompt is passed positionally with a ~120 KB pre-flight guard — long prompts raise `InvalidOptions(code="config.prompt_too_long")` before spawn so you don't hit `OSError: [Errno 7] Argument list too long`. `captures_sessions` is `False`; resume is not supported.

### Options

- `force` — when `True`, appends `--force` so cursor does not block on per-tool permission prompts. Cursor's equivalent of Claude's `dangerously_skip_permissions`. Default `False`.

### parse_stream

Decodes cursor's `tool_call` events and delegates Claude-compatible `assistant`/`result` event shapes to Claude's parser.

### When to use

- Cursor-driven workflows where session capture isn't required.

## `copilot`

```python
from eden import copilot

agent = copilot("claude-sonnet-4", effort="high")
```

### Signature

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

Builds `copilot -p <prompt> --output-format json --model <model> [--allow-all-tools] [--effort <level>] [extra_args ...]`. Prompt is delivered via `-p` (still argv); same ~120 KB pre-flight guard as `cursor()`. `captures_sessions` is `False`; resume is not supported.

### Options

- `effort` — reasoning-effort level (`"low"`, `"medium"`, `"high"`). When set, threads `--effort <level>` into the invocation.
- `allow_all_tools` — when `True`, appends `--allow-all-tools` so Copilot does not block on per-tool permission prompts. Copilot's equivalent of Claude's `dangerously_skip_permissions`. Default `False`.

### parse_stream

Decodes Copilot JSONL events: `assistant.message_delta` → `text`, `tool.execution_start` → `tool_call` (normalises lowercase `"bash"` → `"Bash"` for parity with the other agents), `result` → `session_id`, `error`/`agent_error` → `text`.

### When to use

- GitHub-Copilot-driven workflows; the only first-party big-vendor CLI Eden ships outside of Claude.

## `cli_agent`

```python
from eden import cli_agent

agent = cli_agent(
    name="my-tool",
    model="some-model",
    binary="my-tool",
    extra_args=("--quiet",),
)
```

### Signature

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

All arguments are keyword-only.

- `name` — agent identifier (used in `StreamEvent.agent_name`). Required.
- `model` — informational model identifier. Required (no default).
- `binary` — executable name resolved through `$PATH` at subprocess-spawn time. Required.
- `build_argv` — override the default argv; receives the [`IterationContext`](python-api.md#iterationcontext). Default produces `[binary, *extra_args, ctx.prompt]`.
- `parse_stream` — override the default line-to-`StreamEvent` parser. Default returns `None` (orchestrator falls back to emitting a `text` event per line).
- `captures_sessions` — opt-in to the session post-processing the orchestrator runs for `claude_code`. Default `False`.
- `env` — per-agent environment additions. Merged by the orchestrator.
- `extra_args` — inserted between the binary and the prompt by the default `build_argv`.

### What binary it wraps

Whatever you pass as `binary`. The codex/opencode/pi factories are 5-line wrappers over `cli_agent` that fix `binary=` and a default `model=`.

### When to use

- Any line-streaming CLI agent Eden doesn't ship a dedicated factory for.
- Integrating internal or experimental agents — wire them up via `cli_agent` first; promote to a dedicated factory once they stabilise.
- Custom argv shapes or stream parsers (pass `build_argv=` and `parse_stream=`).

## See also

- [Agent factories](agent-factories.md) — `simulated_agent` and `claude_code`.
- [Agents](agents.md) — factory matrix, Flox runtimes, and authentication.
- [Python API: Agents](python-api-agents.md) — public Protocol and session helper reference.
