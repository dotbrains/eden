# Python API

Canonical index for everything importable from the top-level `eden` package. Detailed reference content is split by topic so this page stays navigable while preserving the public API contract checked by `tests/unit/test_docs_consistency.py`.

---

## Importing

Eden's surface is a single module. Import what you need from `eden`; nothing private is part of the contract.

```python
from eden import (
    AbortController, AbortSignal, Aborted, Agent, AgentError, BindMountSandboxHandle,
    BranchStrategy, ClaudeSessionStorage, CloseResult, CodexSessionStorage, Commit, ConfigError,
    CopyToWorktreeError, CreateOptions, CwdError, Display, DisplayEntry, EdenError,
    EdenTimeoutError, EnvMergeError, ExecResult, FileDisplay, FinalizeResult, FloxEnvError,
    Hook, HookError, HookFailed, HookPhase, HookTimeout, Hooks,
    HostHooks, IdleTimeout, InteractiveResult, InvalidOptions, IsolatedSandboxHandle, Iteration,
    IterationContext, Logging, Mount, Output, OutputDefinition, PiSessionStorage,
    PromptError, RestAuthError, RestError, RestNotFoundError, RestRateLimited, RichDisplay,
    RunResult, Sandbox, SandboxHandle, SandboxHooks, SandboxProvider, SessionCaptureFailed,
    SessionNotFound, SessionStorage, ShutdownCallback, SilentDisplay, StepTimeout, StreamEvent,
    StructuredOutputError, Timeouts, Usage, __version__, claude_code, claude_host_session_path,
    claude_sandbox_session_path, cli_agent, codex, copilot, create_sandbox, create_worktree,
    cursor, encode_project_path, find_claude_session_on_host, find_codex_session_on_host, format_error_message, interactive,
    make_bind_mount_provider, make_isolated_provider, opencode, pi, register_shutdown, run,
    simulated_agent, transfer_session,
)
```

Sandbox providers live alongside the public surface but are imported from `eden.providers` (see [sandbox-providers.md](sandbox-providers.md)) and passed into `run(sandbox=...)`.

## Detailed Reference

- [Entry points](python-api-entrypoints.md) — `run`, `interactive`, caller-managed `Sandbox`, and `create_worktree`.
- [Types and streaming](python-api-types.md) — configuration dataclasses, result types, structured output, and `StreamEvent`.
- [Agents and sessions](python-api-agents.md) — agent Protocols, built-in factories, transcript capture, and session helpers.
- [Extensibility](python-api-extensibility.md) — hooks, cancellation, provider Protocols, and display sinks.
- [Errors and tracing](python-api-errors-tracing.md) — error formatting, tracing, and version metadata.

## Public Surface

### Entry Points

- [`run`](python-api-entrypoints.md#run)
- [`interactive`](python-api-entrypoints.md#interactive)
- [`InteractiveResult`](python-api-entrypoints.md#interactiveresult)
- [`create_sandbox`](python-api-entrypoints.md#create_sandbox)
- [`create_worktree`](python-api-entrypoints.md#create_worktree)
- [`Sandbox`](python-api-entrypoints.md#sandboxexec)

### Configuration

- [`Timeouts`](python-api-types.md#timeouts)
- [`Logging`](python-api-types.md#logging)
- [`Mount`](python-api-types.md#mount)
- [`BranchStrategy`](python-api-types.md#branchstrategy)

### Results

- [`CloseResult`](python-api-types.md#closeresult)
- [`RunResult`](python-api-types.md#runresult)
- [`Iteration`](python-api-types.md#iteration)
- [`Commit`](python-api-types.md#commit)
- [`Usage`](python-api-types.md#usage)
- [`FinalizeResult`](python-api-types.md#finalizeresult)

### Structured Output and Streaming

- [`Output`](python-api-types.md#output)
- [`OutputDefinition`](python-api-types.md#outputdefinition)
- [`StreamEvent`](python-api-types.md#streamevent)

### Agents and Sessions

- [`Agent`](python-api-agents.md#agent-protocol)
- [`IterationContext`](python-api-agents.md#iterationcontext)
- [`simulated_agent`](python-api-agents.md#simulated_agent)
- [`claude_code`](python-api-agents.md#claude_code)
- [`codex`](python-api-agents.md#codex)
- [`opencode`](python-api-agents.md#opencode)
- [`pi`](python-api-agents.md#pi)
- [`cursor`](python-api-agents.md#cursor)
- [`copilot`](python-api-agents.md#copilot)
- [`cli_agent`](python-api-agents.md#cli_agent)
- [`SessionStorage`](python-api-agents.md#session-storage)
- [`ClaudeSessionStorage`](python-api-agents.md#claudesessionstorage)
- [`CodexSessionStorage`](python-api-agents.md#codexsessionstorage)
- [`PiSessionStorage`](python-api-agents.md#pisessionstorage)
- [`encode_project_path`](python-api-agents.md#session-lookup-helpers)
- [`claude_host_session_path`](python-api-agents.md#session-lookup-helpers)
- [`claude_sandbox_session_path`](python-api-agents.md#session-lookup-helpers)
- [`find_claude_session_on_host`](python-api-agents.md#session-lookup-helpers)
- [`find_codex_session_on_host`](python-api-agents.md#session-lookup-helpers)
- [`transfer_session`](python-api-agents.md#transfer_session)

### Lifecycle and Cancellation

- [`Hook`](python-api-extensibility.md#hook)
- [`HookPhase`](python-api-extensibility.md#hookphase)
- [`HostHooks`](python-api-extensibility.md#hosthooks)
- [`SandboxHooks`](python-api-extensibility.md#sandboxhooks)
- [`Hooks`](python-api-extensibility.md#hooks)
- [`AbortController`](python-api-extensibility.md#abortcontroller)
- [`AbortSignal`](python-api-extensibility.md#abortsignal)
- [`Aborted`](python-api-extensibility.md#aborted)
- [`register_shutdown`](python-api-extensibility.md#register_shutdowncallback)
- [`ShutdownCallback`](python-api-extensibility.md#shutdowncallback)

### Provider Protocols

- [`SandboxHandle`](python-api-extensibility.md#sandboxhandle)
- [`BindMountSandboxHandle`](python-api-extensibility.md#bindmountsandboxhandle)
- [`IsolatedSandboxHandle`](python-api-extensibility.md#isolatedsandboxhandle)
- [`SandboxProvider`](python-api-extensibility.md#sandboxprovider)
- [`CreateOptions`](python-api-extensibility.md#createoptions)
- [`ExecResult`](python-api-extensibility.md#execresult)
- [`make_bind_mount_provider`](python-api-extensibility.md#make_bind_mount_provider)
- [`make_isolated_provider`](python-api-extensibility.md#make_isolated_provider)

### Display

- [`Display`](python-api-extensibility.md#display)
- [`DisplayEntry`](python-api-extensibility.md#displayentry)
- [`SilentDisplay`](python-api-extensibility.md#silentdisplay)
- [`FileDisplay`](python-api-extensibility.md#filedisplay)
- [`RichDisplay`](python-api-extensibility.md#richdisplay)

### Errors

- [`EdenError`](python-api-errors-tracing.md#errors)
- [`AgentError`](python-api-errors-tracing.md#errors)
- [`ConfigError`](python-api-errors-tracing.md#errors)
- [`CopyToWorktreeError`](python-api-errors-tracing.md#errors)
- [`CwdError`](python-api-errors-tracing.md#errors)
- [`EdenTimeoutError`](python-api-errors-tracing.md#errors)
- [`EnvMergeError`](python-api-errors-tracing.md#errors)
- [`FloxEnvError`](python-api-errors-tracing.md#errors)
- [`HookError`](python-api-errors-tracing.md#errors)
- [`HookFailed`](python-api-errors-tracing.md#errors)
- [`HookTimeout`](python-api-errors-tracing.md#errors)
- [`IdleTimeout`](python-api-errors-tracing.md#errors)
- [`InvalidOptions`](python-api-errors-tracing.md#errors)
- [`PromptError`](python-api-errors-tracing.md#errors)
- [`RestAuthError`](python-api-errors-tracing.md#errors)
- [`RestError`](python-api-errors-tracing.md#errors)
- [`RestNotFoundError`](python-api-errors-tracing.md#errors)
- [`RestRateLimited`](python-api-errors-tracing.md#errors)
- [`SessionCaptureFailed`](python-api-errors-tracing.md#errors)
- [`SessionNotFound`](python-api-errors-tracing.md#errors)
- [`StepTimeout`](python-api-errors-tracing.md#errors)
- [`StructuredOutputError`](python-api-errors-tracing.md#structuredoutputerror)
- [`format_error_message`](python-api-errors-tracing.md#format_error_messageerror)

### Version

- [`__version__`](python-api-errors-tracing.md#__version__)

## Compatibility Anchors

Existing deep links to this file land on the anchors below. Follow each link for the full reference.

- <a id="entry-points"></a><a id="run"></a>[`run(...)`](python-api-entrypoints.md#run)
- <a id="async-api"></a>[Async API](python-api-entrypoints.md#async-api)
- <a id="interactive"></a>[`interactive(...)`](python-api-entrypoints.md#interactive)
- <a id="interactiveresult"></a>[`InteractiveResult`](python-api-entrypoints.md#interactiveresult)
- <a id="create_sandbox"></a>[`create_sandbox(...)`](python-api-entrypoints.md#create_sandbox)
- <a id="sandboxexec"></a>[`Sandbox.exec(...)`](python-api-entrypoints.md#sandboxexec)
- <a id="sandboxrun"></a>[`Sandbox.run(...)`](python-api-entrypoints.md#sandboxrun)
- <a id="sandboxresume-sandboxfork"></a>[`Sandbox.resume(...)` / `Sandbox.fork(...)`](python-api-entrypoints.md#sandboxresume-sandboxfork)
- <a id="create_worktree"></a>[`create_worktree(...)`](python-api-entrypoints.md#create_worktree)
- <a id="configuration-types"></a><a id="timeouts"></a><a id="logging"></a><a id="mount"></a><a id="branchstrategy"></a>[Configuration types](python-api-types.md#configuration-types)
- <a id="result-types"></a><a id="closeresult"></a><a id="runresult"></a><a id="iteration"></a><a id="commit"></a><a id="usage"></a><a id="finalizeresult"></a>[Result types](python-api-types.md#result-types)
- <a id="structured-output"></a><a id="output"></a><a id="outputdefinition"></a>[Structured output](python-api-types.md#structured-output)
- <a id="streaming"></a><a id="streamevent"></a>[Streaming](python-api-types.md#streaming)
- <a id="agents"></a><a id="agent-protocol"></a><a id="iterationcontext"></a><a id="factories"></a><a id="session-storage"></a><a id="claudesessionstorage"></a><a id="codexsessionstorage"></a><a id="pisessionstorage"></a><a id="session-lookup-helpers"></a><a id="transfer_session"></a>[Agents and sessions](python-api-agents.md#agents)
- <a id="lifecycle-hooks"></a><a id="hook"></a><a id="hookphase"></a><a id="hosthooks"></a><a id="sandboxhooks"></a><a id="hooks"></a>[Lifecycle hooks](python-api-extensibility.md#lifecycle-hooks)
- <a id="cancellation"></a><a id="abortcontroller"></a><a id="abortsignal"></a><a id="aborted"></a><a id="register_shutdowncallback"></a><a id="shutdowncallback"></a>[Cancellation](python-api-extensibility.md#cancellation)
- <a id="provider-protocol-re-exports"></a><a id="sandboxhandle"></a><a id="bindmountsandboxhandle"></a><a id="isolatedsandboxhandle"></a><a id="sandboxprovider"></a><a id="createoptions"></a><a id="execresult"></a><a id="make_bind_mount_provider"></a><a id="make_isolated_provider"></a>[Provider Protocol re-exports](python-api-extensibility.md#provider-protocol-re-exports)
- <a id="display"></a><a id="displayentry"></a><a id="silentdisplay"></a><a id="filedisplay"></a><a id="richdisplay"></a>[Display](python-api-extensibility.md#display)
- <a id="errors"></a><a id="format_error_messageerror"></a><a id="structuredoutputerror"></a>[Errors](python-api-errors-tracing.md#errors)
- <a id="tracing"></a>[Tracing](python-api-errors-tracing.md#tracing)
- <a id="version"></a><a id="__version__"></a>[Version](python-api-errors-tracing.md#version)
