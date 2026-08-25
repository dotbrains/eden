# ADR 0019 — Sandbox capabilities, ports, and background exec

**Status:** Accepted (2026-08-25).

## Context

Comparing Eden against [opencoredev/sandbox-sdk](https://github.com/opencoredev/sandbox-sdk)
(a TypeScript multi-provider sandbox SDK) surfaced four features worth porting:
structured/retryable errors with secret redaction, declarative provider
capabilities, port exposure (preview URLs), and non-blocking background process
handles distinct from blocking `exec()`.

Provider research against real APIs (not guesses):

- **Daytona** — ports, background exec via sessions, and network policy exist on
  the documented `/toolbox/{sandbox_id}` REST surface.
- **Vercel** — ports and detached commands exist on the real API (`POST
  /v4/sandboxes`, session-based `/v2/sandboxes/sessions/{sessionId}/cmd`).
  Eden's prior `/v1/sandboxes/*` endpoints were empirically guessed and wrong;
  fixing them is a prerequisite for Vercel ports/background exec.
- **forkd** — port exposure and background exec are absent from the public SDK
  (confirmed from source, not inferred from E2B). Capabilities are declared
  unsupported by design.

## Decision

### Structured errors + redaction

- `EdenError.retryable` class attribute; `RestError` and `SandboxError`
  subclasses set per-type defaults (`ContainerStartTimeout`, `ExecTimeout` →
  `True`; most others → `False`).
- New `eden/_redact.py` (`redact_secrets`) — zero eden-internal imports to
  avoid cycles with `eden/logging/_redact.py`.
- `RestError.body` / `.url` and sandbox error messages redact at construction.

### Capability map

Flat dict keyed by `provider.name` in `eden/providers/_capabilities.py`.
`capabilities_for()` returns fully-unsupported defaults for unknown providers —
no break for third-party `SandboxProvider` implementations.

### Optional composable Protocols

Follow `IsolatedSandboxHandle` / `hasattr(handle, "finalize")` precedent:

- `SupportsPorts.expose_port()` → `ExposedPort`
- `SupportsBackgroundExec.start()` → `SandboxProcess`

### Port models

- **Dynamic** (`no_sandbox`, `isolated`, `daytona`) — runtime `expose_port`.
- **Static** (`docker`, `podman`, `vercel`) — declare `ports=` at factory
  create; docker/podman map with `-p 127.0.0.1::<port>`; undeclared ports
  raise `PortNotDeclared`.
- **Unsupported** (`forkd`) — no method; `capabilities_for(...).ports ==
  "unsupported"`.

### Background process shapes

Unified at `SandboxProcess` Protocol only:

1. **Local** (`no_sandbox`, `docker`, `podman`, `isolated`) — shared
   `LocalProcess` wrapping `subprocess.Popen` with drain threads.
2. **Daytona** — session + async command REST tier; `kill()` is session-scoped.
3. **Vercel** — detached `cmd` with per-command `kill()`.

### Bundled fixes

- Vercel endpoint migration to v4 create + v2 session cmd/delete.
- forkd `cwd=` removed from SDK kwargs (never supported); prefixed into the
  shell command string instead.

## Consequences

- Public exports: `ProviderCapabilities`, `capabilities_for`, `ExposedPort`,
  `ProcessStatus`, `SandboxProcess`, `SupportsPorts`, `SupportsBackgroundExec`.
- `eden/sandboxes/` top-level file budget is full (15/15); further sandbox
  modules must use subpackages or `eden/providers/`.
- Docs split: `docs/sandbox-capabilities.md`, `docs/python-api-capabilities.md`
  (main provider matrix doc is at line budget).
