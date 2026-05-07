# ADR 0012 — OpenTelemetry tracing

**Status:** Accepted (2026-05-07).

## Context

Production users want to know *what eden is doing* during a long-running iteration loop:

- A sandbox.create call that hangs for 90 seconds — was it docker pulling the image, or `OnSandboxReady` running `npm install`?
- An iteration that aborts with `IdleTimeout` after 10 minutes — when did the agent actually go silent? What tools was it using before that?
- A `RestRateLimited` from a cloud provider — did we already burn a retry budget elsewhere this run?

Three options were considered:

1. **Roll a custom tracing format.** Eden defines its own span shape, exposes a `Tracer` Protocol, ships a stdout / file emitter. Lightweight but every consumer writes their own bridge to whatever observability stack they actually use (Datadog, Honeycomb, OpenTelemetry, plain JSON).
2. **Adopt OpenTelemetry as the contract.** Eden emits OTel spans. Users pip-install `opentelemetry-sdk` plus the exporter of their choice (OTLP / Jaeger / Honeycomb / etc.) and configure it themselves. Eden never sees the exporter.
3. **Use stdlib `logging` with structured records.** Logs are not traces — no parent / child relationships, no precise per-step durations, no easy reconstruction of nested call paths. Cheaper to implement but answers fewer questions.

## Decision

Adopt option 2.

- Eden's runtime depends on the OpenTelemetry **API** package (`opentelemetry-api`), not the SDK. The API package alone is ~80 KB pure-python with no transitive dependencies; it's shipped as the lightest possible "spans-emit-into-the-void" surface. Without the SDK installed and configured, OpenTelemetry's `NoOpTracerProvider` swallows every span — eden code emits identically whether tracing is wired up or not.
- A small `eden.tracing.span(name, **attributes)` context manager is the only public surface. Internally it grabs the global tracer and starts a current-span. Users who want traces install `opentelemetry-sdk` plus an exporter and call `trace.set_tracer_provider(...)` once at process start; eden's spans flow into whatever they configured.
- The instrumented sites are deliberately narrow:
  - `eden.run` — outermost span around a `run()` call. Attributes: `agent.name`, `agent.model`, `sandbox.name`, `sandbox.kind`, `branch`, `max_iterations`.
  - `eden.iteration` — per-iteration child span. Attributes: `iteration.index`. On exit: `usage.input_tokens`, `usage.output_tokens`, `completion_signal`.
  - `eden.sandbox.create` — child of `eden.run` covering provider `create()` + `OnSandboxReady` hooks.
  - `eden.hook` — fires for each lifecycle hook with `hook.phase` and `hook.command` attributes.
  - `eden.agent.exec` — child of `eden.iteration` covering the agent subprocess from spawn to completion.
  - `eden.rest.request` — child span emitted by `RestClient` for each HTTP request, with `http.method`, `http.url`, `http.status_code`, `http.retry_count`.
- Errors are recorded on the span via `record_exception()` and the span status is set to `ERROR`; eden's typed exceptions surface as the recorded exception type so users filtering on `exception.type == "IdleTimeout"` works without bespoke instrumentation.
- Every span auto-derives two metrics from its name: a counter (`<span>.count`) and a histogram (`<span>.duration_seconds`). Both carry an `outcome` attribute (`ok` / `error`). Spans answer "what happened in this run?"; metrics answer "how is the loop performing over time?". Users who installed an SDK already get both — no extra wiring.

## Consequences

- Users who care about observability get a one-import wire-up: `pip install opentelemetry-sdk opentelemetry-exporter-otlp` plus three lines of bootstrap code in their entry point. Spans land in whatever backend they already run.
- Users who don't care pay nothing — `NoOpTracer` is a hot-path-friendly object that returns a `NonRecordingSpan` for `start_as_current_span`; the per-call overhead is a single attribute lookup plus a `with` statement that does nothing.
- Eden does not ship any exporter, sampler, or propagator. Configuration is entirely the user's. This is OTel's idiomatic shape.
- The `opentelemetry-api` dependency is required (not optional) so users always get well-defined behaviour. The SDK and exporters remain optional. If users want to remove the API package too they can patch `eden.tracing.span` to a no-op themselves; that's a niche case not worth a config flag.
- `eden.tracing` is internal-by-default; the `span` helper is exposed under `eden.tracing` for users who want to instrument their own code with the same tracer name (`"eden"`), but the API surface is intentionally tiny.
- Span names use dotted lowercase per OTel conventions (`eden.run`, not `EdenRun`). Attribute keys follow OTel's HTTP / RPC semantic-convention style where it overlaps; eden-specific keys are namespaced (`agent.*`, `sandbox.*`, `iteration.*`, `hook.*`).

## See also

- [`docs/python-api.md` — Tracing](../python-api.md#tracing).
- `eden/tracing/__init__.py` — implementation.
- OpenTelemetry semantic conventions — https://opentelemetry.io/docs/specs/semconv/
