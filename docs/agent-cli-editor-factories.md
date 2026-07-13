# Agent CLI editor factories

Reference for CLI-backed editor agents. See [Agent CLI factories](agent-cli-factories.md)
for `codex`, `opencode`, and `pi`.

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

- `force` — appends `--force` so cursor does not block on per-tool permission prompts. Default `False`.

### parse_stream

Decodes cursor's `tool_call` events and delegates Claude-compatible `assistant`/`result` event shapes to Claude's parser.

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
- `allow_all_tools` — appends `--allow-all-tools` so Copilot does not block on per-tool permission prompts. Default `False`.

### parse_stream

Decodes Copilot JSONL events: `assistant.message_delta` → `text`, `tool.execution_start` → `tool_call` (normalises lowercase `"bash"` → `"Bash"` for parity with the other agents), `result` → `session_id`, `error`/`agent_error` → `text`.

## See also

- [Agent CLI factories](agent-cli-factories.md) — `codex`, `opencode`, and `pi`.
- [Agent CLI adapter](agent-cli-adapter.md) — generic `cli_agent` reference.
- [Agents](agents.md) — factory matrix and authentication.
