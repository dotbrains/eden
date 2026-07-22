# Agent CLI Other Factories

Reference for the non-Codex `cli_agent`-backed factories. See
[Agent CLI factories](agent-cli-factories.md) for `codex` and
[Agent CLI adapter](agent-cli-adapter.md) for the generic adapter.

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

Builds `opencode run --format json --model <model> [--variant <v>] [--agent
<name>] [--dangerously-skip-permissions] [extra_args] <prompt>`. `--format
json` is always present so the bundled stream parser receives structured events;
without it, opencode would emit free-form text and Eden would lose session ids
and tool calls.

For `eden.interactive(...)`, Eden switches to the opencode TUI argv:
`opencode --model <model> [--agent <name>] [extra_args] [--prompt <seed>]`.

`captures_sessions` is `False`. No `OpenCodeSessionStorage` ships today, though
the parser does surface `step_start` events so `Iteration.session_id` populates.

### Options

- `variant` - reasoning-effort variant passed via `--variant`.
- `agent` - named agent mode passed via `--agent`, such as `"build"` or
  `"plan"`.
- `dangerously_skip_permissions` - append `--dangerously-skip-permissions`.
  Safe inside isolated sandboxes; think twice before using `no_sandbox()`.

### parse_stream

Decodes opencode JSONL events: `step_start` -> `session_id`,
`text`/`part.type==text` -> `text`, completed `tool_use` or
`part.type==tool` -> `tool_call`, and `error` -> `text`.

### What binary it wraps

The `opencode` CLI from `sst/opencode`. It must be on `$PATH`. The default
model is illustrative; pass whatever identifier opencode expects.

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

Thin wrapper over [`cli_agent`](agent-cli-adapter.md#cli_agent) with
`binary="pi"` and `name="pi"`. `captures_sessions` is `False`.

### parse_stream

Decodes pi JSONL events: `message_update`/`text_delta` -> `text`,
`tool_execution_start` -> `tool_call` for known tools, `agent_end` ->
final-message `text`, and `agent_error`/`error` -> `text`.

### What binary it wraps

The `pi` CLI from Inflection. It must be on `$PATH`.

## See also

- [Agent CLI factories](agent-cli-factories.md) - Codex factory reference.
- [Agent CLI editor factories](agent-cli-editor-factories.md) - `cursor` and `copilot`.
- [Agent CLI adapter](agent-cli-adapter.md) - generic `cli_agent` reference.
