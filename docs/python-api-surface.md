# Python API surface

Top-level public names importable from `eden`. See [Python API](python-api.md)
for the canonical index and compatibility anchors.

## Entry Points

- [`run`](python-api-entrypoints.md#run)
- [Async API](python-api-async.md)
- [`interactive`](python-api-entrypoints.md#interactive)
- [`InteractiveResult`](python-api-entrypoints.md#interactiveresult)
- [`create_sandbox`](python-api-sandboxes.md#create_sandbox)
- [`create_worktree`](python-api-sandboxes.md#create_worktree)
- [`Sandbox`](python-api-sandboxes.md#sandboxexec)

## Configuration

- [`Timeouts`](python-api-types.md#timeouts)
- [`Logging`](python-api-logging.md#logging)
- [`Mount`](python-api-types.md#mount)
- [`BranchStrategy`](python-api-types.md#branchstrategy)

## Results

- [`CloseResult`](python-api-results.md#closeresult)
- [`RunResult`](python-api-results.md#runresult)
- [`Iteration`](python-api-results.md#iteration)
- [`Commit`](python-api-results.md#commit)
- [`Usage`](python-api-results.md#usage)
- [`FinalizeResult`](python-api-results.md#finalizeresult)

## Structured Output and Streaming

- [`Output`](python-api-output.md#output)
- [`OutputDefinition`](python-api-output.md#outputdefinition)
- [`StreamEvent`](python-api-streaming.md#streamevent)

## Agents and Sessions

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
- [`SessionStorage`](python-api-sessions.md#session-storage)
- [`ClaudeSessionStorage`](python-api-sessions.md#claudesessionstorage)
- [`CodexSessionStorage`](python-api-sessions.md#codexsessionstorage)
- [`PiSessionStorage`](python-api-sessions.md#pisessionstorage)
- [`encode_project_path`](python-api-sessions.md#session-lookup-helpers)
- [`claude_host_session_path`](python-api-sessions.md#session-lookup-helpers)
- [`claude_sandbox_session_path`](python-api-sessions.md#session-lookup-helpers)
- [`find_claude_session_on_host`](python-api-sessions.md#session-lookup-helpers)
- [`find_codex_session_on_host`](python-api-sessions.md#session-lookup-helpers)
- [`transfer_session`](python-api-sessions.md#transfer_session)

## Lifecycle and Cancellation

- [`Hook`](python-api-lifecycle.md#hook)
- [`HookPhase`](python-api-lifecycle.md#hookphase)
- [`HostHooks`](python-api-lifecycle.md#hosthooks)
- [`SandboxHooks`](python-api-lifecycle.md#sandboxhooks)
- [`Hooks`](python-api-lifecycle.md#hooks)
- [`AbortController`](python-api-lifecycle.md#abortcontroller)
- [`AbortSignal`](python-api-lifecycle.md#abortsignal)
- [`Aborted`](python-api-lifecycle.md#aborted)
- [`register_shutdown`](python-api-lifecycle.md#register_shutdowncallback)
- [`ShutdownCallback`](python-api-lifecycle.md#shutdowncallback)

## Provider Protocols

- [`SandboxHandle`](python-api-extensibility.md#sandboxhandle)
- [`BindMountSandboxHandle`](python-api-extensibility.md#bindmountsandboxhandle)
- [`IsolatedSandboxHandle`](python-api-extensibility.md#isolatedsandboxhandle)
- [`SandboxProvider`](python-api-extensibility.md#sandboxprovider)
- [`CreateOptions`](python-api-extensibility.md#createoptions)
- [`ExecResult`](python-api-extensibility.md#execresult)
- [`make_bind_mount_provider`](python-api-extensibility.md#make_bind_mount_provider)
- [`make_isolated_provider`](python-api-extensibility.md#make_isolated_provider)

## Display

- [`Display`](python-api-display.md#display)
- [`DisplayEntry`](python-api-display.md#displayentry)
- [`SilentDisplay`](python-api-display.md#silentdisplay)
- [`FileDisplay`](python-api-display.md#filedisplay)
- [`RichDisplay`](python-api-display.md#richdisplay)

## Errors

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

## Version

- [`__version__`](python-api-errors-tracing.md#__version__)
