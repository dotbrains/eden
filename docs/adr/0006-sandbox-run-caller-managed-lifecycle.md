# ADR 0006 — `Sandbox.run()`: caller-managed sandbox lifecycle

**Status:** Accepted (2026-05-07).

## Context

The original `eden.run()` owned the full lifecycle for one agent invocation: carve a worktree, create a sandbox handle, loop iterations, finalize, close. That's the right shape for "one agent works one task." It's the wrong shape for multi-agent flows on the same artifact:

- **Sequential reviewer** — implementer commits on a named branch, reviewer reads `git diff` against that branch and adds a follow-up commit. Two `eden.run()` calls on `BranchStrategy.named("foo")` would fail the second time with `BranchExists`. Two calls on different branches break the contract that the reviewer reads the implementer's diff.
- **Plan → execute → merge** — a planner agent emits a plan; the merger agent merges branches the planner doesn't know about yet. They want different prompts but the same starting state and the same container.
- **Implement → test → fix loop** — three agents each handling one phase, sharing a worktree.

Eden needed a `create_sandbox()` that returns a `Sandbox` whose `.run()` method reuses the worktree and container across calls.

Three options were considered:

1. **Add a `reuse_branch=True` flag to `eden.run()`** — when set, skip `BranchExists` on a named branch. Surface-area minimal but doesn't solve the deeper question of who owns the sandbox handle's lifetime, and doesn't help the "share one container across multiple `run()` calls" use case.
2. **Refactor `_run_loop` into composable phases** (worktree carve, sandbox create, loop, finalize, close) and expose them all. Maximum flexibility but huge surface area; users have to assemble five things to do what `run()` does in one.
3. **Add `Sandbox.run()`** as a method on the existing `Sandbox` dataclass, plumbed through a single new `caller_managed` mode in `_run_loop` that skips both creation and teardown. The top-level `eden.run()` keeps its current behaviour; `eden.create_sandbox(...)` plus `sandbox.run(...)` is the new surface for multi-agent flows.

## Decision

Adopt option 3. `_run_loop` accepts optional `existing_worktree` and `existing_handle` parameters; when both are present, it sets `caller_managed = True` and skips:

- worktree creation and the `OnWorktreeReady` hook (caller already triggered these via `create_sandbox`);
- handle creation and the `OnSandboxReady` hook;
- the final `OnClose` hook firings;
- handle and worktree teardown.

`Sandbox.run(...)` mirrors `eden.run(...)` minus `sandbox=` (already bound) and `branch_strategy=` (the sandbox already owns its branch — passing it raises `InvalidOptions`). All the iteration-time machinery (idle watchdog, stream parsing, completion matching, structured-output extraction, session capture, log sink) is identical.

`eden.create_sandbox(...)` is promoted to the top-level public surface. `Sandbox` itself becomes a top-level export so users can type-annotate it.

## Consequences

- A worked example becomes idiomatic:
  ```python
  with eden.create_sandbox(
      sandbox=docker_provider(image="eden:proj"),
      branch_strategy=BranchStrategy.named("eden/feat/x"),
  ) as s:
      impl = s.run(agent=eden.claude_code("..."), prompt_file="implement.md", max_iterations=20)
      if impl.commits:
          s.run(agent=eden.claude_code("..."), prompt_file="review.md", max_iterations=1)
  ```
- The `Sandbox` context-manager exit closes the handle and worktree exactly once, regardless of how many `run()` calls happen inside.
- Users who don't need the multi-call shape pay nothing — `eden.run()` is unchanged.
- The `caller_managed` flag is internal; the public contract is "if you used `create_sandbox`, use `.run()`; if you used `eden.run`, use `eden.run`." No mixed-mode footguns.
- Hooks have asymmetric semantics in caller-managed mode: `OnWorktreeReady` and `OnSandboxReady` fire once during `create_sandbox`, never per-run; `OnIterationStart` / `OnIterationEnd` fire per iteration as usual. Documented at [`Sandbox.run`](../python-api.md#sandboxrun).
- Streamed log files are per-run: each `Sandbox.run()` opens a fresh `FileLogSink` (with a `--- Run started: ... ---` delimiter from ADR 0004's append behaviour). Users get one log file per branch by default, with multiple run delimiters inside.

## See also

- [`docs/python-api.md` — `Sandbox.run`](../python-api.md#sandboxrun).
- `eden/sandboxes/_factory.py`, `eden/orchestrator/_loop.py` (`caller_managed` branches).
