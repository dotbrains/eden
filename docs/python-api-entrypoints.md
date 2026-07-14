# Python API: Entry Points

Detailed reference for Eden entry points, caller-managed sandboxes, and
worktree creation. See [Python API](python-api.md) for the canonical public API
index and [Python API: Async](python-api-async.md) for async wrappers.

---

## Entry points

### `run(...)`

Runs an agent against a sandbox in a managed worktree and returns a `RunResult`. Keyword-only.

```python
def run(
    *,
    agent: Agent,
    sandbox: SandboxProvider,
    prompt: str | None = None,
    prompt_file: str | Path | None = None,
    prompt_args: Mapping[str, str] | None = None,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    branch_strategy: BranchStrategy | None = None,
    max_iterations: int = 1,
    completion_signal: str | list[str] = "<promise>COMPLETE</promise>",
    idle_timeout: float | timedelta = 600.0,
    idle_warning_interval: float | timedelta | None = None,
    completion_timeout: float | timedelta | None = 60.0,
    name: str | None = None,
    hooks: Hooks | None = None,
    timeouts: Timeouts | None = None,
    on_event: Callable[[StreamEvent], None] | None = None,
    logging: Logging | None = None,
    signal: AbortSignal | None = None,
    output: OutputDefinition | None = None,
    resume_session: str | None = None,
    copy_to_worktree: list[str] | None = None,
    throw_on_duplicate_worktree: bool = True,
) -> RunResult: ...
```

Parameters:

- `agent` — anything satisfying the `Agent` Protocol (see Agents below).
- `sandbox` — a `SandboxProvider` (`no_sandbox()`, `docker(...)`, `daytona(...)`, etc.).
- `prompt` / `prompt_file` / `prompt_args` — supply the iteration prompt inline, from a file path, or with `{name}` substitutions; mutually-aware (see [prompts.md](prompts.md)). Exactly one of `prompt` or `prompt_file` is required.
- `cwd` — host path that will be the worktree root's source. Defaults to `Path.cwd()`.
- `env` — extra environment variables forwarded into the agent process.
- `branch_strategy` — one of `BranchStrategy.head()`, `merge_to_head(base)`, `named(branch, base)`. Defaults to a generated `eden/<slug>` branch.
- `max_iterations` — maximum agent loop iterations. Default `1`.
- `completion_signal` — string or list-of-strings whose appearance in agent output stops the loop early. Default `"<promise>COMPLETE</promise>"`.
- `idle_timeout` — seconds (or `timedelta`) of stdout silence before the run aborts with `IdleTimeout`. Default `600.0`.
- `idle_warning_interval` — emit `StreamEvent(type="idle_warning")` every N seconds during idleness. `None` disables.
- `completion_timeout` — seconds (or `timedelta`) to keep draining stdout after the completion signal before terminating a still-open agent process. Default `60.0`; pass `None` to wait until EOF or trailing-output idle. This keeps successful agents from failing with `IdleTimeout` when a child process keeps stdout open after the completion signal.
- `name` — informational tag used in worktree branch slugs and stream events.
- `hooks` — `Hooks(host=..., sandbox=...)` lifecycle bundle. Default `Hooks()`.
- `timeouts` — `Timeouts(...)` per-step deadlines. Default `Timeouts()`.
- `on_event` — callback invoked with every `StreamEvent`. Use to forward to UIs, logs, or queues.
- `logging` — `Logging.file(path, on_agent_stream_event=...)` to mirror events to a log file, or `Logging.stdout(...)` to write them to the host process's stdout (CI-friendly; `RunResult.log_file_path` is then `None`); the optional callback fires for agent-emitted text/tool_call/usage/session_id events (plus `raw` when `verbose=True`) and swallows exceptions. Pass `verbose=True` to also surface each literal stdout line as a `raw` event.
- `signal` — `AbortSignal` for cooperative cancellation. If omitted, `run` allocates its own (unused) signal.
- `output` — `Output.object(...)` / `Output.string(...)` to extract a typed payload from a `<tag>` block in stdout. Requires `max_iterations=1` and that `<tag>` literally appear in the prompt. Failure raises [`StructuredOutputError`](#structuredoutputerror).
- `resume_session` — Claude Code session id to resume; appends `--resume <id>` to the agent argv. Requires `max_iterations=1`.
- `copy_to_worktree` — list of host-relative file/directory paths to copy from `cwd` into the freshly-carved worktree before the sandbox boots (and before `host.on_worktree_ready` hooks fire, so hooks can use the copied files). Files preserve their relative path; directories copy recursively; existing destinations are overwritten. Absolute paths, `..` traversal, and the `head` branch strategy raise `InvalidOptions`; missing sources raise `CopyToWorktreeError`. Useful for seeding `.env` files, fixtures, or local configs that the worktree shouldn't inherit from `git checkout`.
- `throw_on_duplicate_worktree` — when `False` and the named-strategy branch already has an on-disk worktree, that worktree is reused (and `close()` does not remove it). Default `True` (raise `BranchExists` on duplicate). Only meaningful for `BranchStrategy.named(...)`. Useful for iterative re-runs against the same scenario branch without `eden clean` in between. On reuse, a clean worktree is fast-forwarded to `origin/<branch>` (`git fetch` + `git merge --ff-only`) so the re-run isn't against stale code; a dirty worktree, a detached HEAD, a missing/unreachable origin, or a diverged branch are all reused as-is.

Returns a `RunResult`.

### Async API

Moved to [Python API: Async](python-api-async.md).

Compatibility anchor:

<a id="async-api"></a>

### Interactive sessions

Moved to [Python API: Interactive](python-api-interactive.md).

Compatibility anchors:

<a id="interactive"></a>
<a id="interactiveresult"></a>

- [`interactive(...)`](python-api-interactive.md#interactive)
- [`InteractiveResult`](python-api-interactive.md#interactiveresult)

## Caller-managed sandboxes and worktrees

Moved to [Python API: Sandboxes and Worktrees](python-api-sandboxes.md).

Compatibility anchors:

<a id="create_sandbox"></a>
<a id="sandboxexec"></a>
<a id="sandboxrun"></a>
<a id="sandboxresume-sandboxfork"></a>
<a id="create_worktree"></a>

- [`create_sandbox(...)`](python-api-sandboxes.md#create_sandbox)
- [`Sandbox.exec(...)`](python-api-sandboxes.md#sandboxexec)
- [`Sandbox.run(...)`](python-api-sandboxes.md#sandboxrun)
- [`Sandbox.resume(...)` / `Sandbox.fork(...)`](python-api-sandboxes.md#sandboxresume-sandboxfork)
- [`create_worktree(...)`](python-api-worktrees.md#create_worktree)
