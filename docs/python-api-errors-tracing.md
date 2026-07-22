# Python API: Errors and Tracing

Detailed reference for error formatting, tracing, and version metadata. See [Python API](python-api.md) for the canonical public API index.

---

## Errors

Every error eden raises descends from `EdenError`. Each concrete class accepts a `cause` keyword argument and carries `code`, `message`, and `hint` attributes for structured logging. `EdenTimeoutError` additionally subclasses the built-in `TimeoutError` for mixed-`except` ergonomics. See [errors.md](errors.md) for the full taxonomy with `code` strings, raise sites, and recovery guidance.

### `format_error_message(error)`

```python
from eden import EdenError, format_error_message, run

try:
    run(agent=..., sandbox=..., prompt="...")
except EdenError as e:
    print(format_error_message(e))
```

Maps any `EdenError` (including the sandbox / worktree subclasses) to a single multi-line user-friendly string of the form:

    <kind-prefix>: <message>
      code: <code>
      hint: <hint>

`hint` is preserved when the error already carries one (e.g. `InvalidOptions(..., hint=...)`). For tagged provider errors that don't carry a hint — `ProviderUnavailable`, `ImageNotFound`, `ContainerStartFailed`, `ExecTimeout`, etc. — the formatter synthesises a context-aware suggestion ("Is Docker running?", "Build the image first: `docker build ...`", "Increase `Timeouts.iteration_step`"). Use this in CLI surfaces so users get the same recovery message regardless of which error subclass surfaced.

The 20 concrete error classes re-exported from `eden`:

- `EdenError` — base class for everything.
- `AgentError` — the agent subprocess exited non-zero without hitting the completion signal. Carries `agent_name`, `exit_code`, `stdout`, `stderr`, and `parsed_error` (extracted from stdout for Codex / Pi / OpenCode, which surface errors there rather than on stderr).
- `ConfigError` — bad arguments, env, or cwd; raised before any side-effect.
- `CopyToWorktreeError` — a worktree copy failed. Raised in two places: (1) the isolated provider's worktree clone failed or exceeded `Timeouts.copy_to_worktree`; (2) a `copy_to_worktree=` entry passed to `run()` / `create_sandbox()` / `interactive()` doesn't exist on disk, or the copy hit a permissions / disk-space error. Carries `source`, `target`, `timeout`, and `timed_out` (true on budget overrun, false on missing-source / permission / disk failure).
- `CwdError` — invalid `cwd=` (missing, not a directory, not in a git repo).
- `EdenTimeoutError` — base for time-budget exceedances; subclasses `TimeoutError`.
- `EnvMergeError` — conflicting `env` overrides between caller, agent, and provider.
- `FloxEnvError` — an agent declared a `flox_env` that can't be activated: the directory has no `.flox/env/manifest.toml`, or the `flox` binary isn't on `PATH`. Raised before the first iteration (fail-fast). Set `EDEN_ALLOW_NO_FLOX=1` to skip activation when `flox` is unavailable. Code `config.flox_env`.
- `HookError` — base for hook failures.
- `HookFailed` — a hook command exited non-zero.
- `HookTimeout` — a hook exceeded `Timeouts.hook_step` (or its own `timeout`).
- `IdleTimeout` — agent stdout was silent past `idle_timeout` before any completion signal was seen. After a completion signal, `completion_timeout` bounds the success-path drain instead.
- `InvalidOptions` — generic kwarg validation failure.
- `PromptError` — `prompt`/`prompt_file`/`prompt_args` resolution failed. Carries `exit_code` for non-zero shell-block exits and `timeout` for shell-block timeouts.
- `RestAuthError` — 401/403 from a cloud provider's REST API.
- `RestError` — base for any non-2xx REST response (or `status=0` connection failure).
- `RestNotFoundError` — 404 from a cloud provider.
- `RestRateLimited` — 429 after retries were exhausted.
- `SessionCaptureFailed` — the orchestrator could not locate or read a session JSONL; soft failure surfaced as a warning event.
- `SessionNotFound` — raised at run start when `resume_session=<id>` references a JSONL that does not exist on the host filesystem. The orchestrator runs this precheck before spawning the agent so the failure surfaces host-side with the expected path, rather than buried in agent stderr. Carries `session_id`, `agent_name`, optional `expected_path`, and `hint`.
- `StepTimeout` — an iteration exceeded `Timeouts.iteration_step`.
- <a id="structuredoutputerror"></a>`StructuredOutputError` — `output=Output.{object,string}(...)` failed to extract or validate. Carries `tag`, `raw_matched` (the matched contents or `None`), `branch`, `commits` produced before extraction failed, optional `preserved_worktree_path`, and — when the failing iteration was captured — `session_id` and `session_file_path` so claude_code callers can resume that conversation with corrective feedback via `resume_session=`. Raised on missing tag, invalid JSON, or schema validation failure.

---

## Tracing

Eden emits OpenTelemetry spans for the iteration loop, sandbox lifecycle, hooks, and REST requests. The runtime depends on `opentelemetry-api>=1.20`; without an installed SDK, OTel's no-op tracer makes every span a zero-cost noop. To collect traces in your application, install `opentelemetry-sdk` and configure a provider/exporter — eden picks up whatever provider is set globally.

Spans emitted:

| Span | Where | Key attributes |
| --- | --- | --- |
| `eden.run` | one per `eden.run()` / `eden.aio.run()` call | `agent.name`, `agent.model`, `sandbox.name`, `sandbox.kind`, `branch`, `max_iterations`, `caller_managed`, `iterations`, `completion_signal` |
| `eden.sandbox.create` | wraps `Sandbox.create` + `OnSandboxReady` hooks | `sandbox.name`, `sandbox.kind`, `branch` |
| `eden.agent.exec` | one per agent invocation (per iteration) | `agent.name`, `agent.model`, `iteration.index`, `branch` |
| `eden.hook` | one per host or sandbox hook command | `hook.location` (`host`/`sandbox`), `hook.phase`, `hook.command`, `hook.timeout_s` |
| `eden.rest.request` | one per `RestClient` HTTP request | `http.method`, `http.url`, `http.status_code`, `http.retry_count` |

All spans record exceptions via `Span.record_exception()` and set status to `ERROR` on raise — failures show up in your trace UI without extra wiring.

Every span also emits two metrics derived from its name:

- `<span>.count` — counter, attribute `outcome` ∈ `{ok, error}`.
- `<span>.duration_seconds` — histogram, same `outcome` attribute.

So `eden.run.count{outcome="error"}` gives you the failure rate across runs, and `eden.agent.exec.duration_seconds` (P50/P95) tells you whether iterations are getting slower over time. Wire up an OTel `MeterProvider` alongside the `TracerProvider` to receive them.

A minimal SDK setup for local debugging:

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor

provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(provider)

import eden
eden.run(agent=..., sandbox=..., prompt="...")
```

See [ADR 0012](adr/0012-otel-tracing.md) for the design rationale and instrumented site list.

---

## Version

### `__version__`

```python
import eden
print(eden.__version__)
```

`eden.__version__` exposes the installed package version (read via `importlib.metadata`). Unit tests assert the value matches `pyproject.toml`.
