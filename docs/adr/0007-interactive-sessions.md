# ADR 0007 — Interactive sessions: TTY-attached, no loop

**Status:** Accepted (2026-05-07).

## Context

Most of eden's value is the orchestrated iteration loop: stream parsing, idle detection, completion-signal matching, session capture. None of those apply when a developer wants to drop into an interactive Claude Code session inside a clean worktree. They want the agent's TUI on their terminal, not eden's machinery.

Three options were considered:

1. **`eden.run(interactive=True)`** — overload the existing function. Cheap, but most of `run()`'s parameters become meaningless (max_iterations, completion_signal, idle_timeout, on_event), and the return type would have to fork.
2. **A separate `eden.interactive()` function** — explicit signature with only the parameters that make sense. Clean public surface; clear that the iteration-loop machinery is not running.
3. **A REPL command in the CLI** — `eden interactive --agent claude-code`. UX for end users, but the Python API is more flexible and the CLI shell can be a thin wrapper later.

## Decision

Adopt option 2. `eden.interactive(agent, sandbox, prompt, ...)` carves a worktree, runs `OnWorktreeReady` / `OnSandboxReady` hooks, then `subprocess.run(argv)` with stdio inherited from the parent process. Returns `InteractiveResult(branch, exit_code, worktree_path, cwd)`.

Key shape decisions:

- **No iteration loop.** The function returns when the agent exits. Users who want a loop wrap the call themselves.
- **No idle watchdog, no stream parsing, no completion matching, no session capture.** These all assume a pipe; an inherited TTY breaks the abstraction.
- **Prompt is optional.** Many interactive uses are "open Claude in this branch with no preset prompt." When supplied, the prompt goes through eden's renderer (`{{SOURCE_BRANCH}}` etc.) and is passed to the agent's `build_interactive_command(ctx)` if defined, falling back to `build_command(ctx)`.
- **Default branch strategy is `head`** when the provider supports it. Interactive sessions usually want their writes to land in the host repo directly; `merge_to_head` (eden's default for bind-mount providers in `run()`) would put writes in a temporary worktree that gets merged on close, which is not the interactive UX.
- **Bind-mount providers (`no_sandbox`, `docker`, `podman`) all expose a TTY.** The handle's `interactive_exec(argv, cwd, env)` method abstracts the binding — `no_sandbox` runs the argv natively, `docker` / `podman` wrap it in `<binary> exec -it`. Isolated providers (Daytona, Vercel, the local `isolated` copy) don't implement `interactive_exec` and raise `InvalidOptions` from the orchestrator with a clear hint. Design recorded separately in [ADR 0009](0009-containerized-tty-for-interactive.md).

Agents can override the argv shape per-mode. `claude_code._ClaudeCodeAgent.build_interactive_command(ctx)` drops `--print`, `--output-format stream-json`, and `-p -`; the user gets the standard claude TUI. The optional prompt is appended positionally as a seed.

## Consequences

- `eden.interactive` and `eden.run` have parallel surfaces: same agent / sandbox / prompt machinery, opposite stdio behaviour. Users learn one mental model.
- Hook authors get the same `OnWorktreeReady` / `OnSandboxReady` / `OnClose` lifecycle they're used to.
- The default-to-`head` choice means interactive sessions on `no_sandbox` will refuse if the host repo is dirty, raising `DirtyHostBlocked`. Users who want to start a session anyway can pass `BranchStrategy.merge_to_head()` explicitly.
- Agents that don't define `build_interactive_command` reuse `build_command(ctx)`. For `cli_agent`-based agents (codex, opencode, pi) this is fine — their argv is a single shape. For agents that pipe prompts via stdin in non-interactive mode (claude_code), the override is required and provided.
- The deferred container-TTY work doesn't block this entry point from shipping. `no_sandbox` is the most common case for interactive-from-host use anyway.

## See also

- Sandcastle 0.4.6 (`interactive()` API), 0.4.6 (`noSandbox` provider).
- [`docs/python-api.md` — `interactive`](../python-api.md#interactive).
- `eden/orchestrator/_interactive.py`, `eden/agents/claude_code/_agent.py` (`build_interactive_command`).
