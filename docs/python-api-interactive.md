# Python API: Interactive

Reference for terminal-attached Eden sessions. See [Python API](python-api.md) for the canonical public API index and [Python API: Entry points](python-api-entrypoints.md) for `run(...)`.

---

## `interactive(...)`

Run an agent attached to the parent terminal's stdio. There is no iteration loop, no idle watchdog, no completion-signal matching — eden carves a worktree, optionally renders a prompt, and execs the agent. The function returns when the agent process exits.

```python
def interactive(
    *,
    agent: Agent,
    sandbox: SandboxProvider | None = None,
    prompt: str | None = None,
    prompt_file: str | Path | None = None,
    prompt_args: Mapping[str, object] | None = None,
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
- `copy_to_worktree` — same semantics as on [`run()`](python-api-entrypoints.md#run): host-relative paths copied into the worktree before `on_worktree_ready` hooks fire. Incompatible with `BranchStrategy.head()`, which is the default for interactive sessions — pass `branch_strategy=BranchStrategy.merge_to_head()` (or `named(...)`) to use it.
- `collect_args` — when the rendered prompt references `{{KEY}}` placeholders not supplied via `prompt_args`, eden prompts the user via stdin for each missing key instead of raising `PromptError`. Defaults to autodetect: collect when `stdin` is a TTY, skip otherwise (so CI runs hit the normal error). Pass `True` / `False` to force.
- `signal` cancels the interactive subprocess. Pre-aborted signals raise before setup; mid-session aborts terminate the process and raise `Aborted`.
- `timeouts` applies to git setup and lifecycle hook phases.

Returns an [`InteractiveResult`](#interactiveresult).

## `InteractiveResult`

```python
@dataclass(frozen=True)
class InteractiveResult:
    branch: str
    exit_code: int
    worktree_path: Path
    cwd: Path
```

Lightweight: `exit_code` is the agent's exit status; `branch` is the worktree branch (`"HEAD"` for the head strategy); `worktree_path` is where the agent ran (commit / inspect from there). No commit list, no stdout — interactive sessions don't capture either.
