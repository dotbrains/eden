# Iteration loop diagram

Sequence diagram for the full `run()` lifecycle.

---

```mermaid
sequenceDiagram
    participant Caller as Caller
    participant Run as run()
    participant Host as HostHooks
    participant Sandbox
    participant SandboxHooks
    participant Agent

    Caller->>Run: run(...)
    Run->>Run: create_worktree()
    Run->>Run: copy_to_worktree (if set)
    Run->>Host: on_worktree_ready
    Run->>Sandbox: create sandbox
    Sandbox->>SandboxHooks: on_sandbox_ready

    loop each iteration (1..max_iterations)
        Run->>Host: on_iteration_start
        Run->>SandboxHooks: on_iteration_start
        Run->>Run: render prompt
        Run->>Agent: build_command(ctx)
        Run->>Sandbox: handle.exec(argv)
        Sandbox-->>Run: stdout stream → StreamEvents
        Note over Agent: agent commits its own work during exec
        Run->>SandboxHooks: on_iteration_end
        Run->>Host: on_iteration_end
        Note over Run: early exit on completion_signal,<br/>idle_timeout, abort, or step_timeout
    end

    Run->>Run: git rev-list base..HEAD → RunResult.commits
    Run->>Sandbox: handle.finalize(target)
    Note right of Sandbox: skipped for bind-mount providers
    Run->>SandboxHooks: on_close
    Run->>Host: on_close
    Run-->>Caller: RunResult
```

## See also

- [How it works](how-it-works.md) — phase-by-phase lifecycle narrative.
- [Prompts](prompts.md) — where prompt rendering fits into the loop.
- [Sandbox providers](sandbox-providers.md) — provider lifecycle details.
