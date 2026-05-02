# ADR 0002 — Sync-first public API

**Status:** Accepted (2026-05-02).

## Context

The original Eden was Rust + Tokio. The Python rewrite faced a choice: expose `async def run(...)` or `def run(...)`?

Arguments for async:
- Aligns with modern Python idioms.
- Composes with FastAPI / async tooling without an event-loop wrapper.

Arguments for sync:
- The dominant use case is "one host process orchestrates one agent run."
- Subprocess + threading already gives us concurrency primitives that compose with sync code.
- An async wrapper over a sync core is trivial; a sync wrapper over an async core requires either `asyncio.run()` (forbids re-entry) or `nest_asyncio` (fragile).

## Decision

Make the public API sync. Use `subprocess.Popen` + `threading.Event` + `Queue` internally. Provide no built-in async wrapper; users who need one can `asyncio.to_thread(eden.run, ...)`.

## Consequences

- Callers don't need an event loop running.
- Re-entrancy works inside Jupyter, REPLs, scripts, and pytest without ceremony.
- Lifecycle hooks are sync callables — straightforward to author.
- Multi-agent parallelism is the user's responsibility (use `concurrent.futures.ThreadPoolExecutor` or `asyncio.to_thread`).
- A future async API can land additively without breaking the sync surface.
