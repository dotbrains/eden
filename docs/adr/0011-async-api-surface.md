# ADR 0011 — Async API surface

**Status:** Accepted (2026-05-07).

## Context

ADR 0002 made the public API sync. The reasoning held: the dominant use case is "one host process orchestrates one agent run," and the internals are `subprocess` + `threading.Event` + `Queue` — primitives that work cleanly under sync code. Twelve months later, three classes of caller want to `await eden.run(...)` without wrapping every call in `asyncio.to_thread`:

- **Web services** orchestrating agents from FastAPI / Starlette handlers want one syntactic layer.
- **Notebook authors** running agents from `await`able cells (`%autoawait` enabled) hit the same friction.
- **Multi-agent fan-out code** that already coordinates with `asyncio.gather(...)` would prefer awaiting eden alongside everything else.

Three options were considered:

1. **Async-ify the core.** Replace `subprocess.Popen` with `asyncio.create_subprocess_exec`; replace `Queue` reads with `asyncio.Queue`; replace `threading.Event` with `asyncio.Event`. Provide `eden.aio.run(...)` natively async, then a sync `eden.run(...)` wrapper that calls `asyncio.run(_aio_run(...))`. Reverses ADR 0002. Forces the sync surface to exist inside an event loop, which breaks Jupyter / `pytest -p no:asyncio` use cases that ADR 0002 explicitly preserved.
2. **Add a thin `eden.aio` namespace** whose functions wrap the sync API in `asyncio.to_thread`. Non-breaking — sync stays the way it is. The async functions delegate the blocking work to a worker thread and `await` its completion. Composable with `asyncio.gather`. Concurrency-bounded by `asyncio`'s default thread pool (`ThreadPoolExecutor` of `min(32, cpu+4)`); users override with `asyncio.set_default_executor` if they need more.
3. **Document the `asyncio.to_thread` recipe in `docs/python-api.md`.** Don't ship any new symbols. Cheapest, but every async caller writes the same boilerplate, and the recipe doesn't compose with type checkers (callers lose `RunResult` typing without explicit annotations).

## Decision

Adopt option 2. Ship `eden.aio` containing async wrappers around `eden.run`, `eden.create_sandbox`, and `eden.interactive`. Each wrapper has the same signature as its sync counterpart and returns the same value type — `eden.aio.run` returns `RunResult`, `eden.aio.create_sandbox` returns `Sandbox`, `eden.aio.interactive` returns `InteractiveResult`. The implementations are one line each: `return await asyncio.to_thread(<sync_fn>, **kwargs)`.

Three intentional non-decisions:

- **No async core refactor.** ADR 0002 still applies. The sync API doesn't need an event loop; Jupyter / REPL re-entrancy keeps working.
- **No `Sandbox.run_async` method.** Adding async methods to a frozen-ish dataclass leaks `asyncio` into the sync surface. Users who want to `await s.run(...)` write `await asyncio.to_thread(s.run, agent=...)` — five extra characters, no surface complexity.
- **No async-only features.** Anything in `eden.aio` is reachable from the sync API too; the namespace is purely a syntactic convenience, not a feature gate.

## Consequences

- Async callers get `await eden.aio.run(...)` with no boilerplate. The wrapped function runs on the asyncio default executor; cancellation propagates via `asyncio.CancelledError` (the wrapper raises immediately when the task is cancelled, leaving the underlying sync call to complete in the worker thread — same semantics as `asyncio.to_thread`).
- Type checkers see the same return types because the wrappers preserve them via direct annotations.
- Concurrency is bounded by the default `ThreadPoolExecutor`. Users running >32 concurrent eden tasks should configure a larger executor — same advice as any `asyncio.to_thread`-heavy code.
- The decision is reversible. If async-native primitives become essential later (e.g. for true cancellation that interrupts a running subprocess), `eden.aio` can grow real implementations behind the same names without breaking existing callers.
- No new runtime dependency: `asyncio.to_thread` is stdlib (Python 3.9+, eden requires 3.11+).
- `eden.aio` is documented alongside the sync API in `docs/python-api.md` rather than as a separate "advanced" page; the symmetry of the interface makes the cross-reference cheaper than splitting.

## See also

- ADR 0002 — the original sync-first decision this refines.
- [`docs/python-api.md` — Async API](../python-api.md#async-api).
- `eden/aio/__init__.py` — the wrappers.
