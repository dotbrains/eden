# ADR 0015 — `create_sandbox(worktree=...)`: split worktree/sandbox ownership

**Status:** Accepted (2026-06-11).

## Context

ADR 0006 gave eden a caller-managed sandbox lifecycle: `create_sandbox()` carves
a worktree, boots a container, and the returned `Sandbox` runs any number of
agents before `close()` tears down both. That couples the worktree's lifetime to
one container. Flows that outlive a single container have no home:

- **Explore, then execute** — poke at a branch interactively (cheap, often
  `no_sandbox`), then hand the same worktree to a containerized AFK run.
- **Different images per phase** — implement under the project image, review
  under a leaner one, on the same branch and files.
- **Crash isolation** — if a container wedges, close it and boot a fresh one
  over the same in-progress worktree instead of losing the branch state.

Upstream models this with `createWorktree()` returning a worktree object whose
`createSandbox()` splits ownership: `sandbox.close()` kills the container only,
`wt.close()` cleans the worktree. Eden already had the standalone
`eden.create_worktree()` (returning `WorktreeHandle`), but no way to feed the
handle back into the sandbox factory.

Two options were considered:

1. **Methods on `WorktreeHandle`** (`wt.run()`, `wt.create_sandbox()`), matching
   upstream's object-oriented surface. Reads nicely but inverts eden's layering
   — `eden.worktree` would import the orchestrator and sandbox factory, creating
   the cycle the package split exists to prevent.
2. **A `worktree=` parameter on `create_sandbox()`**, keeping the existing
   functional surface: the handle flows forward, ownership is recorded on the
   returned `Sandbox`.

## Decision

Adopt option 2. `create_sandbox(worktree=wt)` skips the carve and boots the
container over the caller's worktree. The returned `Sandbox` carries
`owns_worktree=False`; its `close()` (and context-manager exit) closes the
handle only. Self-carved sandboxes keep `owns_worktree=True` and the existing
close-both behaviour — callers who don't pass `worktree=` see no change.

`worktree=` is mutually exclusive with `branch`/`branch_strategy`/`base_branch`
(the branch was fixed at carve time; accepting both would invite silent
disagreement). The provider-side `supports_strategy` check is skipped — there is
no strategy to check; providers only consume `CreateOptions`. The head-style
guard survives structurally: `copy_to_worktree=` is rejected when
`worktree_path == host_repo_path`. On provider `create()` failure the factory
closes only what it carved — a caller-provided worktree is left untouched and
reusable.

## Consequences

- One worktree hosts several sequential sandboxes:
  ```python
  with eden.create_worktree(branch="eden/feat/x") as wt:
      with eden.create_sandbox(sandbox=docker_provider(...), worktree=wt) as s:
          s.run(agent=eden.claude_code("..."), prompt_file="implement.md")
      with eden.create_sandbox(sandbox=docker_provider(image="review:latest"), worktree=wt) as s:
          s.run(agent=eden.claude_code("..."), prompt_file="review.md")
  ```
- Dirty-preservation semantics stay in one place: `WorktreeHandle.close()`
  (preserve if dirty, remove if clean) is the single authority, whoever calls it.
- Concurrent sandboxes over one worktree are NOT made safe by this — the
  worktree advisory lock is held by the handle, not per-sandbox. Sequential
  reuse is the supported shape.
- `eden.aio.create_sandbox` mirrors the parameter (ADR 0011's wrapper contract).

## See also

- ADR 0006 (caller-managed sandbox lifecycle) — this extends it one level.
- Upstream's `createWorktree()` / split-ownership `wt.createSandbox()`.
- `eden/sandboxes/_factory.py`, `eden/worktree/_create.py`.
