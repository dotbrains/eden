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

Moved to [Configuration errors](config-errors.md#configerror).

### `InvalidOptions`

Moved to [Configuration errors](config-errors.md#invalidoptions).

### `PromptError`

Moved to [Configuration errors](config-errors.md#prompterror).

### `EnvMergeError`

Moved to [Configuration errors](config-errors.md#envmergeerror).

### `CwdError`

Moved to [Configuration errors](config-errors.md#cwderror).

### `FloxEnvError`

Moved to [Configuration errors](config-errors.md#floxenverror).

## `HookError`

Moved to [Hook and timeout errors](hook-timeout-errors.md#hookerror).

### `HookFailed`

Moved to [Hook and timeout errors](hook-timeout-errors.md#hookfailed).

### `HookTimeout`

Moved to [Hook and timeout errors](hook-timeout-errors.md#hooktimeout).

## `EdenTimeoutError`

Moved to [Hook and timeout errors](hook-timeout-errors.md#edentimeouterror).

### `IdleTimeout`

Moved to [Hook and timeout errors](hook-timeout-errors.md#idletimeout).

### `StepTimeout`

Moved to [Hook and timeout errors](hook-timeout-errors.md#steptimeout).

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
