# Python API: Logging

Detailed reference for `Logging`, the stream-event sink configuration. See
[Python API: Streaming](python-api-streaming.md) for `StreamEvent`.

## `Logging`

Log sink for `StreamEvent`s: a file (default) or the host process's stdout. For
the file sink, each `run()` opens the file in append mode and prepends a
`--- Run started: <UTC ISO ts> ---` delimiter so shared log files remain
readable.

```python
@dataclass(frozen=True)
class Logging:
    type: Literal["file", "stdout"]
    path: Path | None = None
    level: Literal["debug", "info", "warn", "error"] = "info"
    on_agent_stream_event: Callable[[StreamEvent], None] | None = None
    verbose: bool = False

    @staticmethod
    def file(
        path: str | Path,
        level: ... = "info",
        on_agent_stream_event: Callable[[StreamEvent], None] | None = None,
        verbose: bool = False,
    ) -> Logging: ...

    @staticmethod
    def stdout(
        level: ... = "info",
        on_agent_stream_event: Callable[[StreamEvent], None] | None = None,
        verbose: bool = False,
    ) -> Logging: ...
```

Use `Logging.file("run.log")` to capture every orchestrator event. Use
`Logging.stdout()` to write the same formatted, redacted lines to stdout,
useful in CI; `RunResult.log_file_path` is `None` for stdout-logged runs.
Constructing `Logging(type="file")` without a `path` (or `type="stdout"` with
one) raises `InvalidOptions`.

`on_agent_stream_event` is invoked for every agent-derived event (`text`,
`tool_call`, `usage`, `session_id`, and, when `verbose`, `raw`) in addition to
sink output. Idle warnings and orchestrator-internal text are not forwarded; use
the top-level `on_event` argument to `run()` for those. Callback errors are
swallowed so a broken forwarder cannot kill the run.

`verbose=False` by default. When true, each literal, unparsed agent stdout line
is surfaced as `StreamEvent(type="raw")`, written to the log, and forwarded
through `on_agent_stream_event`.
