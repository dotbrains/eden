# Python API: Streaming

Detailed reference for stream events surfaced by callbacks and logs. See
[Python API: Types](python-api-types.md) for configuration dataclasses and
[Python API: Results](python-api-results.md) for result dataclasses.

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

- `"text"` - line of agent output. Carries `text`.
- `"idle_warning"` - emitted on `idle_warning_interval`. Carries
  `minutes_idle`.
- `"tool_call"` - agent invoked a tool. Carries `tool_name` and `tool_input`.
- `"usage"` - token usage report. Carries `usage` and optionally `session_id`.

`__post_init__` enforces that type-specific fields are non-`None`.
