# What is Eden?

Eden orchestrates AI coding agents inside sandboxed git worktrees so that an agent's edits land on a real branch without contaminating your main checkout.

---

## The problem

When you let an AI agent edit files in your working tree, three things go wrong:

1. **Cross-contamination** — the agent's WIP edits mix with yours.
2. **Untracked side effects** — `pip install`, `npm install`, or schema migrations the agent ran against your real environment.
3. **No commit boundary** — partial work lives in your tree until you decide to keep or discard it.

## How Eden solves it

Eden creates a fresh git worktree on a new branch, mounts it into a container (or syncs it to a remote sandbox), runs the agent inside, captures its output, then commits the changes back. You get a branch with one clean commit per iteration, ready to review or merge.

## Feature matrix

| Capability | Status |
|---|---|
| Local providers (`no_sandbox`, `docker`, `podman`) | Stable |
| Local `isolated` provider (patch-sync) | Stable |
| Cloud providers (`daytona`, `vercel`) | Stable |
| Agents (`claude_code`, `codex`, `opencode`, `pi`, `cli_agent`) | Stable |
| Lifecycle hooks (host + sandbox) | Stable |
| Idle / abort / completion handling | Stable |
| Claude Code session JSONL capture | Stable |
| `eden init` scaffolder | Stable (blank template) |
| Additional `eden init` templates | Roadmap (v0.2+) |
| Real-binary integration tests for `codex`/`opencode`/`pi` | Roadmap (v0.2+) |

## When to use it

Use Eden when you want an agent to make real, committable changes against a real codebase but you don't want it editing the working tree you have open in your editor. It's especially valuable when running multiple agent iterations in parallel.

## When not to use it

Eden does not run agents — it orchestrates them. You still need the agent's CLI installed and authenticated. If you don't have an agent CLI yet, start with `simulated_agent` to learn the orchestrator's shape.

## See also

- [Quick start](quick-start.md)
- [Python API](python-api.md)
- [How it works](how-it-works.md)
