# Agent CLI adapter

Detailed reference for the generic `cli_agent` adapter. See
[Agent CLI factories](agent-cli-factories.md) for dedicated `codex`, `opencode`,
and `pi` wrappers, and [Agent CLI editor factories](agent-cli-editor-factories.md)
for `cursor` and `copilot`.

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

- `name` - agent identifier (used in `StreamEvent.agent_name`). Required.
- `model` - informational model identifier. Required (no default).
- `binary` - executable name resolved through `$PATH` at subprocess-spawn time.
  Required.
- `build_argv` - override the default argv; receives the
  [`IterationContext`](python-api.md#iterationcontext). Default produces
  `[binary, *extra_args, ctx.prompt]`.
- `parse_stream` - override the default line-to-`StreamEvent` parser. Default
  returns `None` (orchestrator emits a `text` event per line).
- `captures_sessions` - opt into the session post-processing the orchestrator
  runs for `claude_code`. Default `False`.
- `env` - per-agent environment additions. Merged by the orchestrator.
- `extra_args` - inserted between the binary and prompt by the default
  `build_argv`.

### What binary it wraps

Whatever you pass as `binary`. The codex/opencode/pi factories are wrappers over
`cli_agent` that fix `binary=` and a default `model=`.

### When to use

- Any line-streaming CLI agent Eden does not ship a dedicated factory for.
- Internal or experimental agents. Start with `cli_agent`; promote to a
  dedicated factory once the shape stabilises.
- Custom argv shapes or stream parsers via `build_argv=` and `parse_stream=`.

## See also

- [Agent CLI factories](agent-cli-factories.md) - dedicated CLI-backed factories.
- [Agent CLI editor factories](agent-cli-editor-factories.md) - editor-backed CLI factories.
- [Python API: Agents](python-api-agents.md) - public Protocol and context types.
