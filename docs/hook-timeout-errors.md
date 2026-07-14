# Hook and Timeout Errors

Detailed reference for lifecycle hook and orchestrator timeout errors. See
[Top-level errors](top-level-errors.md) for other public `EdenError`
subclasses.

## `HookError`

Base for host- and sandbox-hook failures.

### `HookFailed`

A hook's command exited non-zero. Default `code="hook.failed"`. The orchestrator
stops the run after the failing hook; subsequent hooks in the same phase do not
run.

**Recovery:** check `e.cause` (when present) and fix the hook command, or remove
the hook from the bundle.

### `HookTimeout`

A hook exceeded its `timeout` (per-hook override, or `Timeouts.hook_step`).
Default `code="hook.timeout"`.

**Recovery:** raise the timeout with `Timeouts(hook_step=...)` or per-hook
`Hook(..., timeout=...)`, or simplify the hook.

## `EdenTimeoutError`

Base for time-budget exceedances. Subclasses `builtins.TimeoutError`, so
`except TimeoutError:` works too.

### `IdleTimeout`

Agent stdout was silent past `idle_timeout`. Default `code="timeout.idle"`.
Raised by the orchestrator's idle watcher; the partially-completed iteration is
committed before the exception propagates.

**Recovery:** raise `idle_timeout` with `run(idle_timeout=...)`, or investigate
why the agent stopped emitting (network stalls, infinite loops, prompt issues).
`idle_warning_interval` lets you observe the silence in real time before it
trips.

### `StepTimeout`

A single iteration exceeded `Timeouts.iteration_step`. Default
`code="timeout.step"`. Distinct from `IdleTimeout` in that the agent may still
be talking; this fires on total elapsed time, not silence.

**Recovery:** raise `Timeouts(iteration_step=...)`, or split the work across
more iterations.

## See also

- [Python API: Lifecycle](python-api-lifecycle.md) - hook configuration.
- [Python API: Types](python-api-types.md) - timeout configuration.
- [Error recovery](error-recovery.md) - recovery matrix.
