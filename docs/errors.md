# Errors

Every error Eden raises descends from `EdenError`. Catch the base class to handle anything; catch a specific subclass to handle one failure mode.

---

## Conventions

Each concrete error in `eden/errors.py` carries the same shape:

- `code: str` — stable, dotted identifier (e.g. `hook.timeout`, `rest.rate_limited`). Suitable for routing and structured logging.
- `message: str` — human-readable summary.
- `hint: str | None` — optional remediation hint surfaced in the formatted string.
- `cause: Exception | None` — the originating exception, stored as a named attribute. `cause` does **not** set `__cause__`; if you want chained tracebacks, raise with `raise XError(..., cause=e) from e`.

Formatted message shape: `[<code>] <message>` followed by `\nhint: <hint>` when present.

`EdenTimeoutError` additionally subclasses the built-in `TimeoutError`, so `except TimeoutError:` catches Eden's idle/step timeouts alongside any other code's `TimeoutError`s.

The errors below are split into three groups:

1. **Top-level `EdenError` subclasses** — re-exported from `eden`. These are the ones you import and catch in user code.
2. **`SandboxError` family** — raised by sandbox providers in `eden.sandboxes`. Importable from `eden.sandboxes.errors`.
3. **`WorktreeError` family** — raised by `eden.worktree`. Importable from `eden.worktree.errors`.

All three families share `EdenError` as a common ancestor.

## Hierarchy

```
EdenError                                    eden/errors.py
|
+-- ConfigError                              [config bucket]
|   +-- InvalidOptions
|   +-- PromptError
|   +-- EnvMergeError
|   +-- CwdError
|
+-- HookError
|   +-- HookFailed
|   +-- HookTimeout
|
+-- EdenTimeoutError      (also subclass of builtins.TimeoutError)
|   +-- IdleTimeout
|   +-- StepTimeout
|
+-- Aborted
|
+-- SessionCaptureFailed
|
+-- RestError
|   +-- RestAuthError
|   +-- RestNotFoundError
|   +-- RestRateLimited
|
+-- SandboxError                             eden/sandboxes/errors.py
|   +-- ProviderUnavailable
|   +-- ImageNotFound
|   +-- ContainerStartFailed
|   +-- ExecFailed
|   +-- ExecTimeout
|   +-- UnsupportedStrategy
|
+-- WorktreeError                            eden/worktree/errors.py
    +-- WorktreeLocked
    +-- DirtyHostBlocked
    +-- BranchExists
    +-- GitCommandFailed
```

## Top-level errors

### `EdenError`

Base class for everything Eden raises. Catch this to handle any Eden failure uniformly.

```python
from eden import EdenError

try:
    run(...)
except EdenError as e:
    log.error("eden failed: %s", e)
```

### `ConfigError`

Base for problems detected before any side effect — bad arguments, environment, or `cwd`. If you see one of these, nothing was created and nothing was started.

#### `InvalidOptions`

Generic kwarg-validation failure. Carries `code`, `message`, `hint`, `cause`. Raised when the orchestrator detects mutually-exclusive or missing-required arguments to `run(...)` (e.g., supplying both `prompt` and `prompt_file`).

**Recovery:** fix the call site.

#### `PromptError`

Raised when prompt rendering fails — missing `{name}` arg substitution, malformed `!\`shell\`` block, unreadable `prompt_file`, etc. Carries `code`, `message`, `hint`, `cause`.

**Recovery:** inspect `e.code` (e.g. `prompt.missing_arg`, `prompt.shell_failed`) and fix the prompt source.

#### `EnvMergeError`

Conflicting `env` overrides between caller, agent, and provider. Default `code="config.env_merge"`.

**Recovery:** drop the conflicting key from one layer or rename it.

#### `CwdError`

The `cwd=` argument is missing, not a directory, or not inside a git repo. Default `code="config.cwd"`.

**Recovery:** pass a valid path inside a git repo. `cd` into the repo before running, or pass `cwd=Path("/abs/path/to/repo")`.

### `HookError`

Base for host- and sandbox-hook failures.

#### `HookFailed`

A hook's command exited non-zero. Default `code="hook.failed"`. The orchestrator stops the run after the failing hook; subsequent hooks in the same phase do not run.

**Recovery:** check `e.cause` (when present) and fix the hook command, or remove the hook from the bundle.

#### `HookTimeout`

A hook exceeded its `timeout` (per-hook override, or `Timeouts.hook_step`). Default `code="hook.timeout"`.

**Recovery:** raise the timeout with `Timeouts(hook_step=...)` or per-hook `Hook(..., timeout=...)`, or simplify the hook.

### `EdenTimeoutError`

Base for time-budget exceedances. Subclasses `builtins.TimeoutError`, so `except TimeoutError:` works too.

#### `IdleTimeout`

Agent stdout was silent past `idle_timeout`. Default `code="timeout.idle"`. Raised by the orchestrator's idle watcher; the partially-completed iteration is committed before the exception propagates.

**Recovery:** raise `idle_timeout` with `run(idle_timeout=...)`, or investigate why the agent stopped emitting (network stalls, infinite loops, prompt issues). `idle_warning_interval` lets you observe the silence in real time before it trips.

#### `StepTimeout`

A single iteration exceeded `Timeouts.iteration_step`. Default `code="timeout.step"`. Distinct from `IdleTimeout` in that the agent may still be talking — this fires on total elapsed time, not silence.

**Recovery:** raise `Timeouts(iteration_step=...)`, or split the work across more iterations.

### `Aborted`

Raised when cooperative cancellation lands — usually via `AbortController.abort()` from another thread, or by `AbortSignal.raise_if_aborted()` inside a hook. Carries `reason: str` (default `"abort-signal"`).

**Recovery:** intentional. Treat the same as a successful early exit; partial commits are preserved.

### `SessionCaptureFailed`

The orchestrator could not locate, read, or write the Claude Code session JSONL. Default `code="session.capture_failed"`. **Soft failure** — the orchestrator catches it internally and surfaces a warning event instead of aborting the run; you only see this exception if you opt into stricter handling.

**Recovery:** none required — the run completes. Inspect `e.cause` for `OSError`/`PermissionError` if you need to diagnose.

### `RestError`

Base for non-2xx responses from cloud-provider REST APIs (`daytona`, `vercel`, future cloud providers). Carries the standard fields plus:

- `status: int` — HTTP status (`0` for connection-level failures with no HTTP response).
- `body: str` — response body if available.
- `url: str` — request URL.

Default `code="rest.error"`. Catch this at the orchestrator boundary; never let the provider's `requests.RequestException` leak through.

#### `RestAuthError`

401 / 403 — Bearer token rejected or insufficient permissions. Default `code="rest.auth"`.

**Recovery:** rotate or refresh the API token (`DAYTONA_API_KEY`, `VERCEL_TOKEN`, etc.); verify the org/team scope.

#### `RestNotFoundError`

404 — sandbox, project, or file does not exist on the cloud side. Default `code="rest.not_found"`. Notably, `daytona`/`vercel` `close()` swallows this for the sandbox-delete call (idempotent teardown).

**Recovery:** the resource is gone; treat as terminal unless the resource ID is known-stale, in which case stop using it.

#### `RestRateLimited`

429 — server-side rate-limit; eden's automatic retries were exhausted. Default `code="rest.rate_limited"`.

**Recovery:** retry with backoff, parallelize fewer runs, or upgrade the provider plan.

## Sandbox errors

Live in `eden/sandboxes/errors.py`. All inherit `SandboxError` (which inherits `EdenError`). These are not re-exported from the top-level `eden` package — import from `eden.sandboxes.errors` if you need to catch a specific one. Catching `EdenError` works for all of them.

### `SandboxError`

Base for sandbox-provider errors. Catch when you do not care which provider stage failed.

### `ProviderUnavailable`

The provider needs a binary or credential that is not available. Carries `provider: str` and `binary: str`. Raised at `create()` time, not at factory time, so users can import providers without credentials in scope.

Examples: `docker`/`podman` binary not on `PATH`; `DAYTONA_API_KEY` unset; `VERCEL_TOKEN` unset.

**Recovery:** install the missing binary, set the missing env var, or pass the credential to the provider factory directly.

### `ImageNotFound`

`docker run` reported the image is not present locally. Carries `image: str` and `stderr: str`.

**Recovery:** build or pull the image (`docker build -t <name> .` / `docker pull <name>`) before running.

### `ContainerStartFailed`

`docker run` started the container but the container exited non-zero before becoming usable. Carries `image`, `exit_code`, `stderr`.

**Recovery:** check the `stderr` for the failure cause; usually a missing entrypoint, broken image, or insufficient mount permissions.

### `ExecFailed`

`handle.exec(cmd)` returned a non-zero exit code (raised when the caller invokes `ExecResult.check()`, or from internal cloud-provider operations). Carries `result: ExecResult` and `argv_or_cmd: str`.

**Recovery:** inspect `e.result.stderr` and `e.result.exit_code`; fix the command or the sandbox state.

### `ExecTimeout`

`handle.exec(cmd, timeout=...)` exceeded its timeout. Carries `cmd`, `timeout`, `partial_stdout`, `partial_stderr`.

**Recovery:** raise the per-call timeout, or shorten the command.

### `UnsupportedStrategy`

The chosen `BranchStrategy` is not supported by this provider. Carries `provider: str` and `strategy: StrategyTag`.

**Recovery:** pick a different `branch_strategy` (e.g. `BranchStrategy.merge_to_head()`) or switch providers.

## Worktree errors

Live in `eden/worktree/errors.py`. All inherit `WorktreeError` (which inherits `EdenError`). Not re-exported from the top-level package — import from `eden.worktree.errors` if you need to catch a specific one.

### `WorktreeError`

Base for worktree-creation failures.

### `WorktreeLocked`

Another `eden` process holds the per-branch advisory lock. Carries `lock_path: Path` and `holder_pid: int`. Stale locks (PID dead) are wiped automatically on the next acquisition; this exception only fires when the holder is alive.

**Recovery:** wait for the other run to finish, kill it, or use a different branch.

### `DirtyHostBlocked`

`BranchStrategy.head()` requires a clean host repo, but yours has uncommitted changes. Carries `host_repo_path: Path` and `dirty_files: tuple[str, ...]` (first 10).

**Recovery:** commit, stash, or discard the dirty files; or switch to `BranchStrategy.merge_to_head()` / `BranchStrategy.named()`, both of which work with a dirty host.

### `BranchExists`

`BranchStrategy.named(branch=...)` was called with a branch that already exists in the host repo. Carries `branch: str`.

**Recovery:** delete the existing branch, pick a different name, or switch to `merge_to_head()` (which generates a fresh `eden/<slug>` name).

### `GitCommandFailed`

A `git` subprocess invoked by `eden.worktree` exited non-zero. Carries `argv: tuple[str, ...]`, `exit_code: int`, `stderr: str`. Usually wraps a deeper repository issue (corrupted index, missing remote, permission problem).

**Recovery:** read `e.stderr`; fix the underlying repo issue and rerun.

## Recovery patterns at a glance

| Error | Strategy |
|---|---|
| `ConfigError` (any subclass) | Fix the call site / config; re-run. |
| `HookFailed` / `HookTimeout` | Fix the hook command or raise the timeout. |
| `IdleTimeout` / `StepTimeout` | Raise `idle_timeout` / `Timeouts.iteration_step`, or investigate the agent. |
| `Aborted` | Intentional cancellation; treat as success. |
| `SessionCaptureFailed` | Already non-fatal; ignored unless you opt into stricter handling. |
| `RestRateLimited` | Retry with backoff. |
| `RestAuthError` | Rotate credentials. |
| `RestNotFoundError` | Resource is gone; do not retry the same ID. |
| `RestError` (other) | Inspect `e.status` / `e.body`; usually transient. |
| `ProviderUnavailable` | Install the missing binary / set the missing env var. |
| `ImageNotFound` | Build or pull the image. |
| `ContainerStartFailed` | Inspect `e.stderr`; fix the image. |
| `ExecFailed` / `ExecTimeout` | Inspect `e.result.stderr`; fix the command or raise the timeout. |
| `UnsupportedStrategy` | Pick a supported `BranchStrategy` or switch providers. |
| `WorktreeLocked` | Wait, kill the holder, or change branch. |
| `DirtyHostBlocked` | Commit / stash / discard, or switch branch strategy. |
| `BranchExists` | Pick a different branch name. |
| `GitCommandFailed` | Read `e.stderr`; fix the repo. |

## Catching everything

```python
from eden import EdenError, run

try:
    result = run(...)
except EdenError as e:
    code = getattr(e, "code", None)  # not every error carries a code
    log.error("eden failure (code=%s): %s", code, e)
    raise
```

For structured logging, every error in `eden/errors.py` (top-level group, except `Aborted` and `EdenError`/`HookError`/`EdenTimeoutError`/`RestError` bases) exposes `code`, `message`, and `hint` attributes — read them directly. The `SandboxError` and `WorktreeError` families instead expose typed fields specific to the failure (e.g. `e.image`, `e.holder_pid`).

## See also

- [Python API: Errors](python-api.md#errors) — the 16 public error classes by name.
- [Python API: Cancellation](python-api.md#cancellation) — `AbortController` / `AbortSignal` / `Aborted`.
- [Configuration](configuration.md) — env vars whose absence raises `ProviderUnavailable`.
- [Sandbox providers](sandbox-providers.md) — which provider raises which `SandboxError` subclass.
- [How it works](how-it-works.md) — where each error fires in the iteration loop.
