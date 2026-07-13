# Python API: Entry Points

Detailed reference for Eden entry points, caller-managed sandboxes, and worktree creation. See [Python API](python-api.md) for the canonical public API index.

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

`eden.aio` mirrors the three top-level entry points (`run`, `create_sandbox`, `interactive`) as `async def` functions. Each is a thin `asyncio.to_thread` wrapper around its sync counterpart — same arguments, same return type, no async-native primitives in the core. See [ADR 0011](adr/0011-async-api-surface.md).

```python
import asyncio
import eden
from eden import aio
from eden.sandboxes.no_sandbox import provider as no_sandbox

async def main() -> None:
    # Single run.
    result = await aio.run(
        agent=eden.simulated_agent(output="hi\n<promise>COMPLETE</promise>\n"),
        sandbox=no_sandbox(),
        prompt="x",
        max_iterations=1,
    )

    # Concurrent runs.
    a, b = await asyncio.gather(
        aio.run(agent=..., sandbox=..., prompt="task A", branch_strategy=eden.BranchStrategy.named("eden/a")),
        aio.run(agent=..., sandbox=..., prompt="task B", branch_strategy=eden.BranchStrategy.named("eden/b")),
    )

    # create_sandbox.run() is sync; await it via asyncio.to_thread.
    s = await aio.create_sandbox(sandbox=no_sandbox())
    try:
        impl = await asyncio.to_thread(s.run, agent=..., prompt_file="implement.md", max_iterations=20)
    finally:
        s.close()

asyncio.run(main())
```

Concurrency is bounded by asyncio's default `ThreadPoolExecutor` (`min(32, cpu+4)` workers). Users running more concurrent tasks should size the pool with `loop.set_default_executor(...)`. See [ADR 0011](adr/0011-async-api-surface.md) for why eden does not async-ify the core.

### `interactive(...)`

Run an agent attached to the parent terminal's stdio. There is no iteration loop, no idle watchdog, no completion-signal matching — eden carves a worktree, optionally renders a prompt, and execs the agent. The function returns when the agent process exits.

```python
def interactive(
    *,
    agent: Agent,
    sandbox: SandboxProvider | None = None,
    prompt: str | None = None,
    prompt_file: str | Path | None = None,
    prompt_args: Mapping[str, str] | None = None,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    branch_strategy: BranchStrategy | None = None,
    name: str | None = None,
    hooks: Hooks | None = None,
    copy_to_worktree: list[str] | None = None,
    collect_args: bool | None = None,
    signal: AbortSignal | None = None,
    timeouts: Timeouts | None = None,
) -> InteractiveResult: ...
```

- `sandbox` defaults to `no_sandbox()`. `docker(...)` and `podman(...)` are also supported — eden runs the agent argv inside the container via `<binary> exec -it`. Isolated providers (Daytona, Vercel, the local `isolated` copy) raise `InvalidOptions` because they don't expose a TTY.
- `prompt` / `prompt_file` / `prompt_args` are optional. When supplied, the rendered text is passed to the agent's `build_interactive_command(ctx)` (or `build_command(ctx)` when no interactive override exists).
- `branch_strategy` defaults to `BranchStrategy.head()` when the provider supports it — interactive sessions usually want writes to land in the host repo directly. Override to `merge_to_head()` or `named()` for an isolated session.
- `hooks` runs the same `OnWorktreeReady` / `OnSandboxReady` / `OnClose` lifecycle as `run()`; `OnIterationStart` / `OnIterationEnd` are not relevant.
- `copy_to_worktree` — same semantics as on [`run()`](#run): host-relative paths copied into the worktree before `on_worktree_ready` hooks fire. Incompatible with `BranchStrategy.head()`, which is the default for interactive sessions — pass `branch_strategy=BranchStrategy.merge_to_head()` (or `named(...)`) to use it.
- `collect_args` — when the rendered prompt references `{{KEY}}` placeholders not supplied via `prompt_args`, eden prompts the user via stdin for each missing key instead of raising `PromptError`. Defaults to autodetect: collect when `stdin` is a TTY, skip otherwise (so CI runs hit the normal error). Pass `True` / `False` to force.
- `signal` cancels the interactive subprocess. Pre-aborted signals raise before setup; mid-session aborts terminate the process and raise `Aborted`.
- `timeouts` applies to git setup and lifecycle hook phases.

Returns an [`InteractiveResult`](#interactiveresult).

### `InteractiveResult`

```python
@dataclass(frozen=True)
class InteractiveResult:
    branch: str
    exit_code: int
    worktree_path: Path
    cwd: Path
```

Lightweight: `exit_code` is the agent's exit status; `branch` is the worktree branch (`"HEAD"` for the head strategy); `worktree_path` is where the agent ran (commit / inspect from there). No commit list, no stdout — interactive sessions don't capture either.

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
- [`create_worktree(...)`](python-api-sandboxes.md#create_worktree)
