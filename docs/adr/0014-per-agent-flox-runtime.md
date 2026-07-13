# ADR 0014 — Per-agent Flox runtime

**Status:** Accepted (2026-06-10).

## Context

Eden spawns each agent's CLI as a host subprocess from the argv its factory builds: the batch loop builds `argv = agent.build_command(ctx)` and runs it via `_AgentRunner(argv=…, cwd=worktree_path)` (`eden/orchestrator/_loop.py`); the interactive path builds argv the same way and dispatches it through `handle.interactive_exec` (`eden/orchestrator/_interactive.py`). In every case the agent inherits whatever toolchain happens to be on the host `PATH`.

That makes an agent's *runtime* an ambient property of the machine, not part of the agent's definition. Two hosts with different `node`/`python`/CLI versions run "the same" agent differently, and concurrent agents on one host all share the host toolchain.

[Blacksmith](https://github.com/dotbrains/blacksmith/pull/2) solved the equivalent problem by making a Flox env part of each *identity*: every identity ships a `.flox/env/manifest.toml`, the pool launcher activates it (`flox activate -d identities/<id>`) before invoking the harness, and registration refuses an identity whose declared env is missing. Eden already uses Flox for its *own* dev environment (`.flox/`), but not for the agents it spawns.

## Decision

Each agent **type** may declare its own Flox runtime via an optional `flox_env` on its factory (a directory containing `.flox/env/manifest.toml`). When set, the orchestrator wraps the agent argv before execution:

```
flox activate -d <flox_env> -- <agent argv...>
```

Design choices:

- **Granularity: per agent type.** `flox_env` is a factory parameter stored as a public `flox_env` attribute on each agent dataclass. The orchestrator reads it via `getattr(agent, "flox_env", None)`, so the `Agent` Protocol stays minimal and agents without it are untouched. `simulated_agent` runs in-process (no argv exec) and ignores it.
- **Activation: wrap the argv.** A single shared helper, `eden/agents/_flox.py::flox_wrap`, prepends `flox activate -d <dir> --`. It is applied at both seams (loop + interactive) right after `build_command`, before any provider-side `exec` wrapping. This is provider-agnostic and keeps agents ignorant of Flox.
- **Enforced when present.** Declaring `flox_env` is opt-in, but a declared env is validated once, before the first iteration (`validate_flox_env`), and fails fast with `FloxEnvError` (a `ConfigError`, code `config.flox_env`) when the manifest is missing or `flox` is not on `PATH` — the dangling-reference failure blacksmith refuses to register, surfaced at run start instead of mid-run.
- **Escape hatch.** `EDEN_ALLOW_NO_FLOX=1` returns the argv unwrapped when the `flox` binary is absent (Windows, CI legs without Flox), mirroring blacksmith's `BLACKSMITH_ALLOW_NO_FLOX`. A missing manifest still fails — the hatch only covers a missing binary.

## Consequences

- An agent's runtime becomes reproducible and independent of the host: the env's lockfile pins it, and two agents on one host can declare different toolchains.
- Default behavior is unchanged. Agents that don't declare `flox_env` get no wrapping and no validation; existing call sites and tests are unaffected.
- **Container caveat.** For batch runs and `no_sandbox`, the wrap runs on the host. For *interactive* sessions against container providers (`docker`/`podman`), the wrapped argv runs *inside* the container via `interactive_exec`, so `flox` and the env directory must exist in the image. Validation always runs against the host path. Full in-container Flox provisioning is out of scope here.
- The feature is reversible: removing `flox_env` from a factory call restores the prior host-toolchain behavior exactly.

## See also

- [`docs/agent-flox-runtime.md`](../agent-flox-runtime.md) — user-facing reference.
- [`docs/errors.md` — `FloxEnvError`](../errors.md#floxenverror).
- `eden/agents/_flox.py` — `flox_wrap` / `validate_flox_env`.
- Blacksmith PR #2 (the upstream design this mirrors) — https://github.com/dotbrains/blacksmith/pull/2
