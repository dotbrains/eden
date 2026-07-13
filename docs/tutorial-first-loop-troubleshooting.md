# Tutorial first-loop troubleshooting

Common issues while following [Tutorial: build your first agent loop](tutorial-first-loop.md).

## Common gotchas

- **`max_iterations: 1`** — the simple-loop default in older docs is 1, which means the loop runs once and stops regardless of completion. Use `max_iterations: 3` (or higher) so the agent gets a chance to react to test failures across iterations.
- **The agent never terminates** — confirm your prompt asks for the completion signal explicitly, and that the signal is unique enough that intermediate text won't false-match.
- **Branch already exists** — eden refuses to overwrite. Either pass `branch_strategy=BranchStrategy.named(...)` with a fresh name, or delete the leftover branch with `git branch -D <name>`.
- **Agent sees stale files** — when running with `no-sandbox`, the agent has direct access to your current worktree. If you have uncommitted changes in the host repo, the agent sees them. Use `docker` or `podman` for isolation.
