# Agent Flox runtime

Per-agent Flox environments let each CLI-backed factory declare the toolchain it needs instead of inheriting whatever happens to be on the host.

---

## `flox_env`

Every CLI-backed factory (`claude_code`, `codex`, `opencode`, `pi`, `cursor`, `copilot`, `cli_agent`) accepts an optional `flox_env`:

```python
import eden

agent = eden.claude_code(
    model="claude-opus-4-8",
    flox_env="envs/claude",  # a dir containing .flox/env/manifest.toml
)
```

When `flox_env` is set, the orchestrator runs that agent's CLI inside the declared environment by wrapping its argv:

```
flox activate -d <flox_env> -- <agent argv...>
```

This mirrors [blacksmith's per-identity Flox env](https://github.com/dotbrains/blacksmith/pull/2): an agent's runtime is part of its definition, not an ambient property of the machine.

Create one with Flox:

```bash
mkdir -p envs/claude && cd envs/claude && flox init
flox install nodejs   # whatever the agent CLI needs
```

## Enforcement

Declaring a `flox_env` is opt-in, but once declared it is enforced. Eden validates it once, before the first iteration, and fails fast with [`FloxEnvError`](errors.md#floxenverror) when:

- the directory has no `.flox/env/manifest.toml` (a dangling reference), or
- the `flox` binary is not on `PATH`.

Agents that don't set `flox_env` are unchanged: no wrapping, no validation.

## Escape hatch

Set `EDEN_ALLOW_NO_FLOX=1` to skip activation when `flox` is unavailable (Windows, or CI legs without Flox). The agent then runs with the host toolchain, as if no `flox_env` were declared. A missing manifest still fails; the escape hatch only covers a missing `flox` binary.

## Sandbox interaction

For batch runs (`eden.run()`) and `no_sandbox`, the wrap runs on the host. In interactive sessions against container providers (`docker`/`podman`), the wrapped argv runs inside the container via `interactive_exec`, so `flox` and the env directory must exist in the image. Validation always runs against the host path.

## See also

- [Agents](agents.md) — factory matrix and authentication notes.
- [ADR 0014](adr/0014-per-agent-flox-runtime.md) — design rationale.
