# Python API: Structured Output

Detailed reference for schema-validated payloads returned from `run()`. See
[Python API: Types](python-api-types.md) for configuration types,
[Python API: Results](python-api-results.md) for result types, and
[Python API: Streaming](python-api-streaming.md) for stream events.

---

## Structured output

### `Output`

Helpers for declaring schema-validated payloads on `run()`.

```python
from eden import Output, run

# String tag — extracts trimmed contents of <answer>...</answer>
result = run(..., output=Output.string(tag="answer"), max_iterations=1, prompt="...<answer>...</answer>...")
print(result.output)  # str

# Object tag — JSON-parses contents (with code-fence unwrap) and runs schema()
def parse(raw: object) -> Plan:
    assert isinstance(raw, dict)
    return Plan(**raw)

result = run(..., output=Output.object(tag="plan", schema=parse), max_iterations=1, prompt="...<plan>...</plan>...")
plan = result.output  # whatever schema returned
```

`Output.object(tag, schema)` extracts the **last** `<tag>...</tag>` pair, strips an optional Markdown code fence (`` ```json ... ``` ``), `json.loads` it, and passes the parsed object to `schema`. The `schema` argument can be:

- a **pydantic v2 `BaseModel` class** — Eden invokes `MyModel.model_validate(parsed)` directly, so `schema=MyModel` works without writing `schema=MyModel.model_validate`;
- a **pydantic v1 `BaseModel` class** — detected via `parse_obj` + `__fields__`, invoked as `MyModel.parse_obj(parsed)`;
- a **dataclass / attrs class** wrapped as `schema=lambda d: MyDataclass(**d)`;
- a **msgspec converter** like `schema=lambda d: msgspec.convert(d, MyType)`;
- any other **callable** of shape `(parsed: object) -> T`.

Detection happens at extraction time via `model_validate` / `parse_obj` getattr — no third-party dependencies are imported. Anything that isn't callable and isn't a recognised validator class raises `TypeError` from `eden.output._validator.resolve_validator`.

`Output.string(tag)` extracts the contents and `.strip()`s them — no JSON, no validation.

Validation at entry:
- `max_iterations == 1` is required (raises `InvalidOptions` otherwise).
- `<tag>` must literally appear in the prompt source (raises `InvalidOptions` otherwise).

Failures during extraction raise [`StructuredOutputError`](python-api-errors-tracing.md#structuredoutputerror) with `tag`, `raw_matched`, `branch`, optional `preserved_worktree_path`, and — when the failing iteration was captured — `session_id` and `session_file_path`. The session fields let claude_code callers resume the same conversation with corrective feedback and re-emit corrected output, rather than restart from scratch:

```python
from eden import Output, StructuredOutputError, claude_code, run

try:
    result = run(
        agent=claude_code(),
        sandbox=..., prompt="emit <result>{...}</result>",
        output=Output.object(tag="result", schema=my_schema),
    )
except StructuredOutputError as e:
    if e.session_id is None:
        raise
    run(
        agent=claude_code(),
        sandbox=..., output=Output.object(tag="result", schema=my_schema),
        resume_session=e.session_id,
        prompt=f"Your previous <result> was malformed: {e.raw_matched!r}. Re-emit it.",
    )
```

**`max_retries` automates that loop.** Pass `Output.object(tag=..., schema=..., max_retries=N)` (or `Output.string(tag=..., max_retries=N)`) and `run()` retries on its own when extraction or validation fails: it resumes the failing session with corrective feedback (the failure message + the tag to re-emit), or — for agents without session capture — re-runs the original prompt, up to `N` extra times before raising `StructuredOutputError`. Default `0` (no retry). A negative value raises `InvalidOptions`.

```python
result = run(
    agent=claude_code(),
    sandbox=..., prompt="emit <result>{...}</result>",
    output=Output.object(tag="result", schema=my_schema, max_retries=2),
)
```

### `OutputDefinition`

Type alias for the union of `Output.object(...)` and `Output.string(...)` return values. Use this in helper signatures that accept either shape.

## See also

- [Python API: Types](python-api-types.md) — configuration types.
- [Python API: Results](python-api-results.md) — result types.
- [Python API: Streaming](python-api-streaming.md) — stream events.
- [Python API: Errors and tracing](python-api-errors-tracing.md) — `StructuredOutputError`.
