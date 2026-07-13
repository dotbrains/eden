# Errors

Every error Eden raises descends from `EdenError`. Catch the base class to handle anything; catch a specific subclass to handle one failure mode.

## Conventions

Each concrete error in `eden/errors.py` carries the same shape:

- `code: str` — stable, dotted identifier (e.g. `hook.timeout`, `rest.rate_limited`). Suitable for routing and structured logging.
- `message: str` — human-readable summary.
- `hint: str | None` — optional remediation hint surfaced in the formatted string.
- `cause: Exception | None` — the originating exception, stored as a named attribute. `cause` does **not** set `__cause__`; if you want chained tracebacks, raise with `raise XError(..., cause=e) from e`.

Formatted message shape: `[<code>] <message>` followed by `\nhint: <hint>` when present.

`EdenTimeoutError` additionally subclasses the built-in `TimeoutError`, so `except TimeoutError:` catches Eden's idle/step timeouts alongside any other code's `TimeoutError`s.

The errors below are split into three groups: top-level `EdenError` subclasses re-exported from `eden`, `SandboxError` subclasses from `eden.sandboxes.errors`, and `WorktreeError` subclasses from `eden.worktree.errors`. All three families share `EdenError` as a common ancestor.

## Hierarchy

```mermaid
classDiagram
    class EdenError
    class TimeoutError {
        <<builtin>>
    }

    class ConfigError
    class HookError
    class EdenTimeoutError
    class Aborted
    class SessionCaptureFailed
    class RestError
    class SandboxError
    class WorktreeError

    EdenError <|-- ConfigError
    EdenError <|-- HookError
    EdenError <|-- EdenTimeoutError
    EdenError <|-- Aborted
    EdenError <|-- SessionCaptureFailed
    EdenError <|-- RestError
    EdenError <|-- SandboxError
    EdenError <|-- WorktreeError
    TimeoutError <|-- EdenTimeoutError

    ConfigError <|-- InvalidOptions
    ConfigError <|-- PromptError
    ConfigError <|-- EnvMergeError
    ConfigError <|-- CwdError
    ConfigError <|-- FloxEnvError

    HookError <|-- HookFailed
    HookError <|-- HookTimeout

    EdenTimeoutError <|-- IdleTimeout
    EdenTimeoutError <|-- StepTimeout

    RestError <|-- RestAuthError
    RestError <|-- RestNotFoundError
    RestError <|-- RestRateLimited

    SandboxError <|-- ProviderUnavailable
    SandboxError <|-- ImageNotFound
    SandboxError <|-- ContainerStartFailed
    SandboxError <|-- ExecFailed
    SandboxError <|-- ExecTimeout
    SandboxError <|-- MountConfigError
    SandboxError <|-- UnsupportedStrategy

    WorktreeError <|-- WorktreeLocked
    WorktreeError <|-- DirtyHostBlocked
    WorktreeError <|-- BranchExists
    WorktreeError <|-- GitCommandFailed
```

Module locations: top-level errors live in `eden/errors.py`, sandbox errors in `eden/sandboxes/errors.py`, and worktree errors in `eden/worktree/errors.py`.

## Top-level errors

Moved to [Top-level errors](top-level-errors.md).

Compatibility anchors: <a id="edenerror"></a><a id="configerror"></a><a id="invalidoptions"></a><a id="prompterror"></a><a id="envmergeerror"></a><a id="cwderror"></a><a id="floxenverror"></a><a id="hookerror"></a><a id="hookfailed"></a><a id="hooktimeout"></a><a id="edentimeouterror"></a><a id="idletimeout"></a><a id="steptimeout"></a><a id="aborted"></a><a id="sessioncapturefailed"></a><a id="resterror"></a><a id="restautherror"></a><a id="restnotfounderror"></a><a id="restratelimited"></a>

- [`EdenError`](top-level-errors.md#edenerror)
- [`ConfigError`](top-level-errors.md#configerror)
- [`InvalidOptions`](top-level-errors.md#invalidoptions)
- [`PromptError`](top-level-errors.md#prompterror)
- [`EnvMergeError`](top-level-errors.md#envmergeerror)
- [`CwdError`](top-level-errors.md#cwderror)
- [`FloxEnvError`](top-level-errors.md#floxenverror)
- [`HookError`](top-level-errors.md#hookerror)
- [`HookFailed`](top-level-errors.md#hookfailed)
- [`HookTimeout`](top-level-errors.md#hooktimeout)
- [`EdenTimeoutError`](top-level-errors.md#edentimeouterror)
- [`IdleTimeout`](top-level-errors.md#idletimeout)
- [`StepTimeout`](top-level-errors.md#steptimeout)
- [`Aborted`](top-level-errors.md#aborted)
- [`SessionCaptureFailed`](top-level-errors.md#sessioncapturefailed)
- [`RestError`](top-level-errors.md#resterror)
- [`RestAuthError`](top-level-errors.md#restautherror)
- [`RestNotFoundError`](top-level-errors.md#restnotfounderror)
- [`RestRateLimited`](top-level-errors.md#restratelimited)

## Sandbox errors

Moved to [Sandbox and worktree errors](sandbox-worktree-errors.md#sandbox-errors).

Compatibility anchors: <a id="sandboxerror"></a><a id="providerunavailable"></a><a id="imagenotfound"></a><a id="containerstartfailed"></a><a id="execfailed"></a><a id="exectimeout"></a><a id="mountconfigerror"></a><a id="unsupportedstrategy"></a>

- [`SandboxError`](sandbox-worktree-errors.md#sandboxerror)
- [`ProviderUnavailable`](sandbox-worktree-errors.md#providerunavailable)
- [`ImageNotFound`](sandbox-worktree-errors.md#imagenotfound)
- [`ContainerStartFailed`](sandbox-worktree-errors.md#containerstartfailed)
- [`ExecFailed`](sandbox-worktree-errors.md#execfailed)
- [`ExecTimeout`](sandbox-worktree-errors.md#exectimeout)
- [`MountConfigError`](sandbox-worktree-errors.md#mountconfigerror)
- [`UnsupportedStrategy`](sandbox-worktree-errors.md#unsupportedstrategy)

## Worktree errors

Moved to [Sandbox and worktree errors](sandbox-worktree-errors.md#worktree-errors).

Compatibility anchors: <a id="worktreeerror"></a><a id="worktreelocked"></a><a id="dirtyhostblocked"></a><a id="branchexists"></a><a id="gitcommandfailed"></a>

- [`WorktreeError`](sandbox-worktree-errors.md#worktreeerror)
- [`WorktreeLocked`](sandbox-worktree-errors.md#worktreelocked)
- [`DirtyHostBlocked`](sandbox-worktree-errors.md#dirtyhostblocked)
- [`BranchExists`](sandbox-worktree-errors.md#branchexists)
- [`GitCommandFailed`](sandbox-worktree-errors.md#gitcommandfailed)

## <a id="recovery-patterns-at-a-glance"></a><a id="catching-everything"></a>Recovery examples

- [Recovery patterns at a glance](error-recovery.md#recovery-patterns-at-a-glance)
- [Catching everything](error-recovery.md#catching-everything)

## See also

- [Python API: Errors](python-api.md#errors) — public error classes by name.
- [Top-level errors](top-level-errors.md) — top-level public error classes.
- [Python API: Cancellation](python-api.md#cancellation) — `AbortController` / `AbortSignal` / `Aborted`.
- [Error recovery](error-recovery.md) — handling strategies and catch-all examples.
- [Sandbox and worktree errors](sandbox-worktree-errors.md) — provider and worktree error families.
- [Sandbox providers](sandbox-providers.md) — which provider raises which `SandboxError` subclass.
- [How it works](how-it-works.md) — where each error fires in the iteration loop.
