# Python API: Sandboxes and Worktrees

Detailed reference for caller-managed sandboxes. See
[Python API: Entry points](python-api-entrypoints.md) for `run(...)`,
`interactive(...)`, and the async wrappers, and
[Python API: Worktrees](python-api-worktrees.md) for standalone worktrees.

---

## `create_sandbox(...)`

Creates a sandbox + worktree once and returns a `Sandbox` whose `.run(...)` method can be called multiple times against the same branch and container. Use when one logical task requires multiple agent runs (implement -> review, plan -> execute, etc.) and you want them to share environment, branch, and any provider-side caches.

```python
def create_sandbox(
    *,
    sandbox: SandboxProvider,
    branch: str | None = None,
    branch_strategy: BranchStrategy | None = None,
    worktree: WorktreeHandle | None = None,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    mounts: tuple[Mount, ...] | None = None,
    name: str | None = None,
    hooks: Hooks | None = None,
    copy_to_worktree: list[str] | None = None,
    timeouts: Timeouts | None = None,
) -> Sandbox: ...
```

`worktree` (when supplied) reuses a caller-managed `WorktreeHandle` from [`create_worktree()`](python-api-worktrees.md#create_worktree) instead of carving a fresh one. Ownership is then split: `Sandbox.close()` tears down the container only, and the caller's `worktree.close()` decides the worktree's fate (preserved if dirty, removed if clean) so one worktree can host several sequential sandboxes. Mutually exclusive with `branch`/`branch_strategy`/`base_branch`.

```python
with eden.create_worktree(branch="eden/feature/x") as wt:
    with eden.create_sandbox(sandbox=docker_provider(...), worktree=wt) as s:
        s.run(agent=eden.claude_code("..."), prompt_file="implement.md")
    # First container is gone; the branch and its files are still on disk.
    with eden.create_sandbox(sandbox=docker_provider(image="review:latest"), worktree=wt) as s:
        s.run(agent=eden.claude_code("..."), prompt_file="review.md")
```

`hooks` runs `host.on_worktree_ready` after `copy_to_worktree`, `sandbox.on_sandbox_ready` after provider creation, and `*.on_close` when `Sandbox.close()` runs.

`copy_to_worktree` (when supplied) seeds host-relative files into the worktree before the sandbox boots, with the same semantics as on [`run()`](python-api-entrypoints.md#run). The copy happens once at `create_sandbox()` time, not on every subsequent `sb.run()`. Incompatible with `BranchStrategy.head()`.

`timeouts` caps the one-time carve's git plumbing via `Timeouts.git_setup` (reused by `Sandbox.close()` for the teardown `git worktree remove`). Per-run deadlines like `iteration_step` are passed separately to each [`Sandbox.run(timeouts=...)`](#sandboxrun).

The returned `Sandbox` is a dataclass with `.worktree`, `.handle`, `.sandbox_provider`, `.cwd`, `.owns_worktree`, plus `.exec(...)` / `.run(...)` / `.resume(...)` / `.fork(...)` methods. `Sandbox.close()` returns a [`CloseResult`](python-api-results.md#closeresult): managed sandboxes report whether their worktree was removed or preserved; caller-owned worktree sandboxes report `released_only`. It also doubles as a context manager: `with create_sandbox(...) as s:` closes the handle, and the worktree too when the sandbox carved it itself (`owns_worktree=True`; `False` for caller-provided worktrees).

## `Sandbox.exec(...)`

Runs an arbitrary command in an existing sandbox and returns the provider's [`ExecResult`](python-api-extensibility.md#execresult). This is useful for setup, inspection, or lightweight commands between agent runs without creating a new container/worktree.

```python
result = s.exec("python -m pytest tests/unit/test_example.py", timeout=120)
if not result.ok:
    result.check()
```

Keyword options mirror `SandboxHandle.exec(...)`: `on_line`, `cwd`, `env`, `timeout`, and `stdin`, plus `sudo=True` to run through `sudo -E -- sh -c` inside the sandbox. `cwd` defaults to the sandbox's configured `cwd`, or the worktree path when no sandbox cwd was configured. Non-zero exit codes are returned, not raised; call `result.check()` for strict behavior.

## `Sandbox.run(...)`

Run an agent against an already-created sandbox. Same arguments as `run()` minus `sandbox=` (already bound) and `branch_strategy=` (would be ignored because the sandbox already owns a branch). All other options carry over: `output=`, `resume_session=`, `fork_session=`, `logging=`, `on_event=`, `signal=`, `hooks=`, `timeouts=`, etc.

Useful for sequential-reviewer / planner-executor patterns where multiple agents share one branch, and for resuming a captured Claude Code session **inside the same container** without re-creating the worktree.

```python
with eden.create_sandbox(sandbox=docker_provider(...), branch="eden/feature/x") as s:
    impl = s.run(agent=eden.claude_code("..."), prompt_file="implement.md", max_iterations=20)
    if impl.commits:
        s.run(agent=eden.claude_code("..."), prompt_file="review.md", max_iterations=1)
```

## <a id="sandboxresume-sandboxfork"></a>`Sandbox.resume(...)` / `Sandbox.fork(...)`

```python
def resume(self, prompt: str, **overrides) -> RunResult: ...
def fork(self, prompt: str, **overrides) -> RunResult: ...
```

Continue (or branch from) the sandbox's **most recent captured session** without threading session ids by hand: `Sandbox` remembers the last `run()`/`resume()`/`fork()` result's `session_id`. `resume()` keeps the same session id; `fork()` starts a fresh id seeded from the parent transcript (leaving the parent untouched, for fanning several follow-ups off one base). Both reuse this container and worktree. `overrides` forward to `run()` (e.g. `agent=`, `output=`, `timeouts=`). Raise `InvalidOptions` if no prior run captured a session.

```python
with eden.create_sandbox(sandbox=docker_provider(...)) as s:
    s.run(agent=eden.claude_code("opus"), prompt="Draft a migration plan.")
    s.resume("Now apply step 1.")          # same session, in the same container
    a = s.fork("Variant A: use Alembic.")  # two independent follow-ups
    b = s.fork("Variant B: raw SQL.")      # both branched from the same base
```

## `create_worktree(...)`

Moved to [Python API: Worktrees](python-api-worktrees.md#create_worktree).
