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
- [Extensibility, errors, and tracing](python-api-extensibility.md) — hooks, cancellation, provider Protocols, display sinks, error formatting, tracing, and version metadata.

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

- [`EdenError`](python-api-extensibility.md#errors)
- [`AgentError`](python-api-extensibility.md#errors)
- [`ConfigError`](python-api-extensibility.md#errors)
- [`CopyToWorktreeError`](python-api-extensibility.md#errors)
- [`CwdError`](python-api-extensibility.md#errors)
- [`EdenTimeoutError`](python-api-extensibility.md#errors)
- [`EnvMergeError`](python-api-extensibility.md#errors)
- [`FloxEnvError`](python-api-extensibility.md#errors)
- [`HookError`](python-api-extensibility.md#errors)
- [`HookFailed`](python-api-extensibility.md#errors)
- [`HookTimeout`](python-api-extensibility.md#errors)
- [`IdleTimeout`](python-api-extensibility.md#errors)
- [`InvalidOptions`](python-api-extensibility.md#errors)
- [`PromptError`](python-api-extensibility.md#errors)
- [`RestAuthError`](python-api-extensibility.md#errors)
- [`RestError`](python-api-extensibility.md#errors)
- [`RestNotFoundError`](python-api-extensibility.md#errors)
- [`RestRateLimited`](python-api-extensibility.md#errors)
- [`SessionCaptureFailed`](python-api-extensibility.md#errors)
- [`SessionNotFound`](python-api-extensibility.md#errors)
- [`StepTimeout`](python-api-extensibility.md#errors)
- [`StructuredOutputError`](python-api-extensibility.md#structuredoutputerror)
- [`format_error_message`](python-api-extensibility.md#format_error_messageerror)

### Version

- [`__version__`](python-api-extensibility.md#__version__)

## Compatibility Anchors

Existing deep links to this file land on the stubs below. Follow each link for the full reference.

## Entry points

### `run(...)`

Moved to [`run(...)`](python-api-entrypoints.md#run).

### Async API

Moved to [Async API](python-api-entrypoints.md#async-api).

### `interactive(...)`

Moved to [`interactive(...)`](python-api-entrypoints.md#interactive).

### `InteractiveResult`

Moved to [`InteractiveResult`](python-api-entrypoints.md#interactiveresult).

### `create_sandbox(...)`

Moved to [`create_sandbox(...)`](python-api-entrypoints.md#create_sandbox).

### `Sandbox.exec(...)`

Moved to [`Sandbox.exec(...)`](python-api-entrypoints.md#sandboxexec).

### `Sandbox.run(...)`

Moved to [`Sandbox.run(...)`](python-api-entrypoints.md#sandboxrun).

### `Sandbox.resume(...)` / `Sandbox.fork(...)`

Moved to [`Sandbox.resume(...)` / `Sandbox.fork(...)`](python-api-entrypoints.md#sandboxresume-sandboxfork).

### `create_worktree(...)`

Moved to [`create_worktree(...)`](python-api-entrypoints.md#create_worktree).

## Configuration types

### `Timeouts`

Moved to [`Timeouts`](python-api-types.md#timeouts).

### `Logging`

Moved to [`Logging`](python-api-types.md#logging).

### `Mount`

Moved to [`Mount`](python-api-types.md#mount).

### `BranchStrategy`

Moved to [`BranchStrategy`](python-api-types.md#branchstrategy).

## Result types

### `CloseResult`

Moved to [`CloseResult`](python-api-types.md#closeresult).

### `RunResult`

Moved to [`RunResult`](python-api-types.md#runresult).

### `Iteration`

Moved to [`Iteration`](python-api-types.md#iteration).

### `Commit`

Moved to [`Commit`](python-api-types.md#commit).

### `Usage`

Moved to [`Usage`](python-api-types.md#usage).

### `FinalizeResult`

Moved to [`FinalizeResult`](python-api-types.md#finalizeresult).

## Structured output

### `Output`

Moved to [`Output`](python-api-types.md#output).

### `OutputDefinition`

Moved to [`OutputDefinition`](python-api-types.md#outputdefinition).

## Streaming

### `StreamEvent`

Moved to [`StreamEvent`](python-api-types.md#streamevent).

## Agents

### `Agent` Protocol

Moved to [`Agent` Protocol](python-api-agents.md#agent-protocol).

### `IterationContext`

Moved to [`IterationContext`](python-api-agents.md#iterationcontext).

### Factories

Moved to [Factories](python-api-agents.md#factories).

### <a id="session-storage"></a>`SessionStorage` Protocol

Moved to [<a id="session-storage"></a>`SessionStorage` Protocol](python-api-agents.md#session-storage).

### `ClaudeSessionStorage`

Moved to [`ClaudeSessionStorage`](python-api-agents.md#claudesessionstorage).

### `CodexSessionStorage`

Moved to [`CodexSessionStorage`](python-api-agents.md#codexsessionstorage).

### `PiSessionStorage`

Moved to [`PiSessionStorage`](python-api-agents.md#pisessionstorage).

### Session Lookup Helpers

Moved to [Session Lookup Helpers](python-api-agents.md#session-lookup-helpers).

### `transfer_session`

Moved to [`transfer_session`](python-api-agents.md#transfer_session).

## Lifecycle hooks

### `Hook`

Moved to [`Hook`](python-api-extensibility.md#hook).

### `HookPhase`

Moved to [`HookPhase`](python-api-extensibility.md#hookphase).

### `HostHooks`

Moved to [`HostHooks`](python-api-extensibility.md#hosthooks).

### `SandboxHooks`

Moved to [`SandboxHooks`](python-api-extensibility.md#sandboxhooks).

### `Hooks`

Moved to [`Hooks`](python-api-extensibility.md#hooks).

## Cancellation

### `AbortController`

Moved to [`AbortController`](python-api-extensibility.md#abortcontroller).

### `AbortSignal`

Moved to [`AbortSignal`](python-api-extensibility.md#abortsignal).

### `Aborted`

Moved to [`Aborted`](python-api-extensibility.md#aborted).

### `register_shutdown(callback)`

Moved to [`register_shutdown(callback)`](python-api-extensibility.md#register_shutdowncallback).

### `ShutdownCallback`

Moved to [`ShutdownCallback`](python-api-extensibility.md#shutdowncallback).

## Provider Protocol re-exports

### `SandboxHandle`

Moved to [`SandboxHandle`](python-api-extensibility.md#sandboxhandle).

### `BindMountSandboxHandle`

Moved to [`BindMountSandboxHandle`](python-api-extensibility.md#bindmountsandboxhandle).

### `IsolatedSandboxHandle`

Moved to [`IsolatedSandboxHandle`](python-api-extensibility.md#isolatedsandboxhandle).

### `SandboxProvider`

Moved to [`SandboxProvider`](python-api-extensibility.md#sandboxprovider).

### `CreateOptions`

Moved to [`CreateOptions`](python-api-extensibility.md#createoptions).

### `ExecResult`

Moved to [`ExecResult`](python-api-extensibility.md#execresult).

### `make_bind_mount_provider`

Moved to [`make_bind_mount_provider`](python-api-extensibility.md#make_bind_mount_provider).

### `make_isolated_provider`

Moved to [`make_isolated_provider`](python-api-extensibility.md#make_isolated_provider).

## Display

### `Display`

Moved to [`Display`](python-api-extensibility.md#display).

### `DisplayEntry`

Moved to [`DisplayEntry`](python-api-extensibility.md#displayentry).

### `SilentDisplay`

Moved to [`SilentDisplay`](python-api-extensibility.md#silentdisplay).

### `FileDisplay`

Moved to [`FileDisplay`](python-api-extensibility.md#filedisplay).

### `RichDisplay`

Moved to [`RichDisplay`](python-api-extensibility.md#richdisplay).

## Errors

### `format_error_message(error)`

Moved to [`format_error_message(error)`](python-api-extensibility.md#format_error_messageerror).

### <a id="structuredoutputerror"></a>`StructuredOutputError`

Moved to [<a id="structuredoutputerror"></a>`StructuredOutputError`](python-api-extensibility.md#structuredoutputerror).

## Tracing

### Tracing

Moved to [Tracing](python-api-extensibility.md#tracing).

## Version

### `__version__`

Moved to [`__version__`](python-api-extensibility.md#__version__).
