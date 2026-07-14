# Python API: Worktrees

Detailed reference for standalone worktree creation. See
[Python API: Sandboxes and Worktrees](python-api-sandboxes.md) for
caller-managed sandboxes that run against a worktree.

## `create_worktree(...)`

Carves a worktree without launching an agent, useful when you want to manage the
iteration loop yourself.

```python
def create_worktree(
    *,
    branch: str | None = None,
    branch_strategy: BranchStrategy | None = None,
    base_branch: str | None = None,
    cwd: str | Path | None = None,
    copy_to_worktree: list[str] | None = None,
    hooks: Hooks | None = None,
    timeouts: Timeouts | None = None,
    name: str | None = None,
    throw_on_duplicate_worktree: bool = True,
) -> WorktreeHandle: ...
```

Provide either `branch` or `branch_strategy`; supplying both raises
`ValueError`. Defaults to `BranchStrategy.merge_to_head()`. `cwd` selects the
host repo instead of `Path.cwd()`. `copy_to_worktree` copies host-relative files
before `host.on_worktree_ready` hooks run. `timeouts.git_setup` controls git
worktree operations and `timeouts.hook_step` controls hooks.

Returns a `WorktreeHandle` with `.branch`, `.worktree_path`, `.close()`,
`.run(...)`, `.interactive(...)`, and `.create_sandbox(...)`. It works as a
context manager.

Use the handle directly when a workflow needs to keep one branch/worktree across
several steps:

```python
from eden.sandboxes.no_sandbox import provider as no_sandbox

with eden.create_worktree(branch="eden/issue-42") as wt:
    explore = wt.interactive(agent=eden.claude_code("..."), sandbox=no_sandbox())
    result = wt.run(
        agent=eden.claude_code("..."),
        sandbox=docker_provider(...),
        prompt_file=".eden/implement.md",
        max_iterations=5,
    )
    with wt.create_sandbox(sandbox=docker_provider(...)) as sb:
        checked = sb.exec("pytest -q", timeout=120)
        checked.check()
```

`wt.run(...)` creates a short-lived sandbox backed by the worktree, runs one
agent loop through
[`Sandbox.run(...)`](python-api-sandboxes.md#sandboxrun), closes only the
sandbox handle, and leaves the worktree open for more work. It accepts the same
options as `Sandbox.run(...)` plus `sandbox=`, provider `mounts=`,
`copy_to_worktree=`, and sandbox-creation `hooks=`.

`wt.interactive(...)` launches an interactive session in the existing worktree
without carving or closing another worktree. It accepts the same
prompt/env/name/hook/signal/timeout options as top-level
[`interactive(...)`](python-api-interactive.md#interactive).

`wt.create_sandbox(...)` is equivalent to
[`create_sandbox(worktree=wt, ...)`](python-api-sandboxes.md#create_sandbox):
each returned `Sandbox.close()` removes only its provider handle; the worktree
lives until `wt.close()`.

## See also

- [Python API: Sandboxes and Worktrees](python-api-sandboxes.md) - `create_sandbox`.
- [Python API: Entry points](python-api-entrypoints.md) - `run` and `interactive`.
