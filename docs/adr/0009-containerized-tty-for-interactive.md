# ADR 0009 — Containerized TTY for `interactive()`

**Status:** Accepted (2026-05-07).

## Context

ADR 0007 shipped `eden.interactive()` for `no_sandbox` only. Other providers raise `InvalidOptions`. Users running interactive Claude Code sessions inside docker / podman containers need a parallel path.

The blocker is that the `SandboxHandle` Protocol only exposes `exec()` for non-interactive command invocations. Interactive sessions need:

- a TTY allocated inside the container (`docker exec -it ...`);
- the parent's stdin / stdout / stderr inherited (no `subprocess.PIPE` capturing);
- the container's working directory and any per-call env vars threaded;
- correct teardown when the user exits the agent (the container persists, only the `exec` exits).

Three options were considered:

1. **Special-case docker / podman in `_interactive.py`** — branch on `provider.name == "docker"` and inline the `docker exec -it` invocation. Quick but couples the orchestrator to a binary name and breaks for any future container provider.
2. **Add `interactive_exec()` to the bind-mount handle Protocol.** Each container provider implements it with its own binary. The orchestrator's `_interactive.py` checks `hasattr(handle, "interactive_exec")` and dispatches; falls back to direct `subprocess.run` for `no_sandbox`. Clean Protocol extension, lets the isolated provider opt out (its handle has nothing to attach to).
3. **Build it as a top-level helper that takes a `SandboxHandle` and an argv** — `eden.exec_interactive(handle, argv, ...)` — and call it from `_interactive.py`. Pushes the same logic into a public surface that's mostly redundant with `interactive()`.

## Decision

Adopt option 2.

- Extend `BindMountSandboxHandle` (the marker Protocol covering docker, podman, no_sandbox) with an optional `interactive_exec(argv, *, cwd=None, env=None) -> int` method that runs the argv with stdio inherited and returns the process exit code.
- `no_sandbox._NoSandboxHandle.interactive_exec` runs `subprocess.run(argv, cwd=cwd, env=env)` directly — the existing `_interactive.py` flow extracted into a method.
- `_ContainerHandle.interactive_exec` builds `[binary, "exec", "-it", "-w", cwd_in_container, "-e", k=v..., container_id, *argv]` and runs it with stdio inherited. The `-it` flag allocates a pseudo-TTY and keeps stdin attached.
- `_interactive.py` drops the `provider.name == "no_sandbox"` gate and instead checks `hasattr(handle, "interactive_exec")`. For containers, the agent argv is built once (via `build_interactive_command`) and passed through; the worktree path is translated to the in-container path (`/workspace`).
- Isolated providers (Daytona, Vercel, our local isolated copy) don't implement `interactive_exec`. Calling `interactive()` against them keeps the original `InvalidOptions` error with an updated hint (something like "isolated providers don't expose a TTY; use docker / podman / no_sandbox").

The `subprocess.run` in `_interactive.py` for `no_sandbox` becomes a single-line wrapper around `handle.interactive_exec(...)`. Hooks (`OnSandboxReady`, `OnClose`) already work for any handle; no changes needed there.

## Consequences

- `eden.interactive(sandbox=docker_provider(...))` becomes a real workflow: drop into a Claude TUI inside a clean worktree inside a container that has the project's deps installed.
- The Protocol extension is opt-in. Existing custom providers that don't implement `interactive_exec` behave exactly as today (raise `InvalidOptions` from the orchestrator with a clear hint). The runtime check is `hasattr`, not `isinstance`.
- Container env propagation matches `exec()`'s shape: each `-e KEY=VALUE` is forwarded. Hooks that prepared the container (e.g. `npm install`) still run before `interactive_exec`.
- Per-call cwd is translated host → container by the orchestrator before invocation. The handle's `worktree_path` (which equals `/workspace` for docker / podman) is the natural default.
- Docker-on-macOS and Docker-on-Windows both support `-it`; Podman requires `--userns=keep-id` for rootless TTY but eden already passes the user via `--user uid:gid` so this is unaffected.

## See also

- ADR 0007 — the no_sandbox-only baseline this builds on.
- `eden/providers/_protocols.py` — `BindMountSandboxHandle` marker.
- `eden/providers/_impl/container.py`, `eden/sandboxes/no_sandbox/__init__.py` — implementation sites.
