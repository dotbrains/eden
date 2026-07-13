# Top-level errors

Detailed reference for top-level `EdenError` subclasses re-exported from
`eden`. See [Errors](errors.md) for the full hierarchy and conventions.

## `EdenError`

Base class for everything Eden raises. Catch this to handle any Eden failure
uniformly.

```python
from eden import EdenError

try:
    run(...)
except EdenError as e:
    log.error("eden failed: %s", e)
```

## `ConfigError`

Base for problems detected before any side effect: bad arguments, environment,
or `cwd`. If you see one of these, nothing was created and nothing was started.

### `InvalidOptions`

Generic kwarg-validation failure. Carries `code`, `message`, `hint`, `cause`.
Raised when the orchestrator detects mutually-exclusive or missing-required
arguments to `run(...)` (for example, supplying both `prompt` and `prompt_file`).

**Recovery:** fix the call site.

### `PromptError`

Raised when prompt rendering fails: missing `{name}` arg substitution, malformed
`!\`shell\`` block, unreadable `prompt_file`, etc. Carries `code`, `message`,
`hint`, `cause`.

**Recovery:** inspect `e.code` (for example, `prompt.missing_arg`,
`prompt.shell_failed`) and fix the prompt source.

### `EnvMergeError`

Conflicting `env` overrides between caller, agent, and provider. Default
`code="config.env_merge"`.

**Recovery:** drop the conflicting key from one layer or rename it.

### `CwdError`

The `cwd=` argument is missing, not a directory, or not inside a git repo.
Default `code="config.cwd"`.

**Recovery:** pass a valid path inside a git repo. `cd` into the repo before
running, or pass `cwd=Path("/abs/path/to/repo")`.

### `FloxEnvError`

An agent declared a `flox_env` that cannot be activated: the directory has no
`.flox/env/manifest.toml`, or the `flox` binary is not on `PATH`. Raised before
the first iteration so a dangling reference surfaces immediately rather than
mid-run. Default `code="config.flox_env"`. See
[agents.md](agents.md#per-agent-flox-runtime).

**Recovery:** point `flox_env` at a directory containing
`.flox/env/manifest.toml`, install Flox so the env can be activated, or set
`EDEN_ALLOW_NO_FLOX=1` to run without it (Windows / CI smoke tests). Drop the
`flox_env` declaration to restore the prior host-toolchain behavior.

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

**Recovery:** raise `Timeouts(iteration_step=...)`, or split the work across more
iterations.

## `Aborted`

Raised when cooperative cancellation lands, usually via `AbortController.abort()`
from another thread, or by `AbortSignal.raise_if_aborted()` inside a hook.
Carries `reason: str` (default `"abort-signal"`).

**Recovery:** intentional. Treat the same as a successful early exit; partial
commits are preserved.

## `SessionCaptureFailed`

The orchestrator could not locate, read, or write the Claude Code session JSONL.
Default `code="session.capture_failed"`. This is a soft failure: the
orchestrator catches it internally and surfaces a warning event instead of
aborting the run; you only see this exception if you opt into stricter handling.

**Recovery:** none required; the run completes. Inspect `e.cause` for
`OSError`/`PermissionError` if you need to diagnose.

## `RestError`

Moved to [REST errors](rest-errors.md#resterror).

Compatibility anchors: <a id="resterror"></a>

### `RestAuthError`

Moved to [REST errors](rest-errors.md#restautherror).

Compatibility anchors: <a id="restautherror"></a>

### `RestNotFoundError`

Moved to [REST errors](rest-errors.md#restnotfounderror).

Compatibility anchors: <a id="restnotfounderror"></a>

### `RestRateLimited`

Moved to [REST errors](rest-errors.md#restratelimited).

Compatibility anchors: <a id="restratelimited"></a>
