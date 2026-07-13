# Python API

Canonical index for everything importable from the top-level `eden` package. Detailed reference content is split by topic so this page stays navigable while preserving the public API contract checked by `tests/unit/test_docs_consistency.py`.

---

## Importing

Eden's surface is a single module. Import what you need from `eden`; nothing
private is part of the contract. The public names are indexed below and covered
by `tests/unit/test_docs_consistency.py`.

Sandbox providers live alongside the public surface but are imported from `eden.providers` (see [sandbox-providers.md](sandbox-providers.md)) and passed into `run(sandbox=...)`.

## Detailed Reference

- [Surface](python-api-surface.md) — top-level public export list.
- [Entry points](python-api-entrypoints.md) — `run`, `interactive`, and async wrappers.
- [Sandboxes and worktrees](python-api-sandboxes.md) — caller-managed `Sandbox` and worktree creation.
- [Types](python-api-types.md) — configuration dataclasses.
- [Results](python-api-results.md) — result dataclasses.
- [Logging](python-api-logging.md) — stream-event sink configuration.
- [Streaming](python-api-streaming.md) — `StreamEvent` callbacks and log events.
- [Structured output](python-api-output.md) — `Output`, `OutputDefinition`, schema validation, and retries.
- [Agents](python-api-agents.md) — agent Protocols and built-in factories.
- [Sessions](python-api-sessions.md) — transcript capture, storage, and session helpers.
- [Lifecycle](python-api-lifecycle.md) — hooks, cancellation, and shutdown callbacks.
- [Extensibility](python-api-extensibility.md) — provider Protocols.
- [Display](python-api-display.md) — display sinks and display entries.
- [Errors and tracing](python-api-errors-tracing.md) — error formatting, tracing, and version metadata.

## Public Surface

See [Python API surface](python-api-surface.md) for the full top-level export list.

## Compatibility Anchors

Existing deep links to this file land on the anchors below. Follow each link for the full reference.

- <a id="entry-points"></a><a id="run"></a>[`run(...)`](python-api-entrypoints.md#run)
- <a id="async-api"></a>[Async API](python-api-entrypoints.md#async-api)
- <a id="interactive"></a>[`interactive(...)`](python-api-entrypoints.md#interactive)
- <a id="interactiveresult"></a>[`InteractiveResult`](python-api-entrypoints.md#interactiveresult)
- <a id="create_sandbox"></a>[`create_sandbox(...)`](python-api-sandboxes.md#create_sandbox)
- <a id="sandboxexec"></a>[`Sandbox.exec(...)`](python-api-sandboxes.md#sandboxexec)
- <a id="sandboxrun"></a>[`Sandbox.run(...)`](python-api-sandboxes.md#sandboxrun)
- <a id="sandboxresume-sandboxfork"></a>[`Sandbox.resume(...)` / `Sandbox.fork(...)`](python-api-sandboxes.md#sandboxresume-sandboxfork)
- <a id="create_worktree"></a>[`create_worktree(...)`](python-api-sandboxes.md#create_worktree)
- <a id="configuration-types"></a><a id="timeouts"></a><a id="mount"></a><a id="branchstrategy"></a>[Configuration types](python-api-types.md#configuration-types)
- <a id="logging"></a>[Logging](python-api-logging.md#logging)
- <a id="result-types"></a><a id="closeresult"></a><a id="runresult"></a><a id="iteration"></a><a id="commit"></a><a id="usage"></a><a id="finalizeresult"></a>[Result types](python-api-results.md#result-types)
- <a id="structured-output"></a><a id="output"></a><a id="outputdefinition"></a>[Structured output](python-api-output.md#structured-output)
- <a id="streaming"></a><a id="streamevent"></a>[Streaming](python-api-streaming.md#streaming)
- <a id="agents"></a><a id="agent-protocol"></a><a id="iterationcontext"></a><a id="factories"></a>[Agents](python-api-agents.md#agents)
- <a id="session-storage"></a><a id="claudesessionstorage"></a><a id="codexsessionstorage"></a><a id="pisessionstorage"></a><a id="session-lookup-helpers"></a><a id="transfer_session"></a>[Sessions](python-api-sessions.md#session-storage)
- <a id="lifecycle-hooks"></a><a id="hook"></a><a id="hookphase"></a><a id="hosthooks"></a><a id="sandboxhooks"></a><a id="hooks"></a>[Lifecycle hooks](python-api-lifecycle.md#lifecycle-hooks)
- <a id="cancellation"></a><a id="abortcontroller"></a><a id="abortsignal"></a><a id="aborted"></a><a id="register_shutdowncallback"></a><a id="shutdowncallback"></a>[Cancellation](python-api-lifecycle.md#cancellation)
- <a id="provider-protocol-re-exports"></a><a id="sandboxhandle"></a><a id="bindmountsandboxhandle"></a><a id="isolatedsandboxhandle"></a><a id="sandboxprovider"></a><a id="createoptions"></a><a id="execresult"></a><a id="make_bind_mount_provider"></a><a id="make_isolated_provider"></a>[Provider Protocol re-exports](python-api-extensibility.md#provider-protocol-re-exports)
- <a id="display"></a><a id="displayentry"></a><a id="silentdisplay"></a><a id="filedisplay"></a><a id="richdisplay"></a>[Display](python-api-display.md#display)
- <a id="errors"></a><a id="format_error_messageerror"></a><a id="structuredoutputerror"></a>[Errors](python-api-errors-tracing.md#errors)
- <a id="tracing"></a>[Tracing](python-api-errors-tracing.md#tracing)
- <a id="version"></a><a id="__version__"></a>[Version](python-api-errors-tracing.md#version)
