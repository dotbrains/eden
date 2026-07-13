# Python API: Display

Detailed reference for display sinks and display entries. See [Python API: Extensibility](python-api-extensibility.md) for lifecycle hooks, cancellation, and provider protocols.

---

## Display

A swappable sink abstraction for orchestrator → user output. Eden re-exports the Protocol and three concrete sinks; pass any of them to higher-level CLI / interactive helpers that accept a `display=` argument. Built on a tagged `DisplayEntry` ADT.

### `Display`

```python
class Display(Protocol):
    def intro(self, title: str) -> None: ...
    def status(self, message: str, severity: Severity = "info") -> None: ...
    def text(self, message: str) -> None: ...
    def text_chunk(self, chunk: str) -> None: ...
    def tool_call(self, name: str, formatted_args: str) -> None: ...
    def summary(self, title: str, rows: Mapping[str, str]) -> None: ...
    @contextmanager
    def spinner(self, message: str) -> Iterator[None]: ...
    @contextmanager
    def task_log(self, title: str) -> Iterator[Callable[[str], None]]: ...
```

`Severity` is one of `"info" | "success" | "warn" | "error"`. `text()` emits a line-oriented message; `text_chunk()` emits raw streaming text with no implied newline, so adjacent chunks render as contiguous prose. The two context managers wrap long-running blocks: `spinner` for an indeterminate progress indicator; `task_log` for collecting per-step messages and emitting them on exit (the yielded callable pushes messages into the log).

### `DisplayEntry`

Tagged-union of `IntroEntry | StatusEntry | SpinnerEntry | SummaryEntry | TaskLogEntry | TextEntry | TextChunkEntry | ToolCallEntry`. Each has a `.tag` literal and the relevant payload fields. Used by `SilentDisplay` to record everything for test assertions.

### `SilentDisplay`

```python
display = SilentDisplay()
# ... orchestrator runs ...
assert display.entries[-1].title == "Run complete"
```

Records every entry on `.entries`, prints nothing. The test sink.

### `FileDisplay`

```python
display = FileDisplay(Path(".eden/logs/run.log"))
```

Append-only file sink with timestamped delimiter on construction. Spinners and task logs record their duration. `text_chunk()` writes chunks verbatim, and later line-oriented entries start on a fresh line if a chunk ended mid-line. Suitable for unattended / CI runs.

### `RichDisplay`

```python
display = RichDisplay()  # uses default rich.console.Console()
```

Live terminal output powered by the bundled `rich` dependency. Renders severities with color glyphs, spinners with `rich.status.Status`, summaries as bold-key / dim-value blocks. Inject a custom `Console` via `RichDisplay(console=Console(file=...))` for capturing tests.

## See also

- [Python API: Extensibility](python-api-extensibility.md) — lifecycle hooks, cancellation, and provider protocols.
- [Python API](python-api.md) — canonical public API index.
