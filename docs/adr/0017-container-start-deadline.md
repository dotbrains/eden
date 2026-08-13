# ADR 0017 — Shared deadline for the docker/podman container-start sequence

**Status:** Accepted (2026-08-13).

## Context

`docker`/`podman`'s `_create()` runs a sequence of host-side subprocess
calls: `<binary> image inspect` (existence), a second inspect for the UID
check, `<binary> run` (the actual container start), and — when a file mount
needs a parent directory created — a `<binary> exec` to `mkdir`/`chown` it.
None of these calls passed a `timeout`, so a stuck daemon, a contended image
pull, or a resource-starved host could hang `eden.run()`/`interactive()`/
`create_sandbox()` indefinitely with no distinct error.

Found via a feature-gap comparison against
[mattpocock/sandcastle](https://github.com/mattpocock/sandcastle) (a
TypeScript analogue of eden with the same bind-mount provider design), whose
`ContainerStartTimeoutError` (`src/errors.ts`) wraps its whole
`provider.create()` call in one `CONTAINER_START_TIMEOUT_MS = 120_000`
budget (`src/startSandbox.ts`) rather than giving each step an independent
one.

## Decision

Bound the whole `_create()` sequence with one shared wall-clock deadline,
matching sandcastle's semantics, rather than giving each subprocess call its
own independent timeout — N independent per-step timeouts could otherwise
cost up to N times the intended deadline in the worst case.

`eden/providers/_impl/container_deadline.py` (`container_start_deadline`) is
a context manager yielding a `remaining()` callable: each subprocess call
passes `timeout=remaining()`, computed fresh against one shared deadline.
`remaining()` itself raises `ContainerStartTimeout` once the budget is
exhausted; the context manager also catches `subprocess.TimeoutExpired`
from a call that ran out of time mid-flight and re-raises the same error.
Both paths carry `binary` and `timeout` for a `docker ps`/`create_timeout=`
recovery hint (`eden/_error_hints.py`).

Exposed as `create_timeout: float = 120.0` on `docker()`/`podman()` —
configurable per sandcastle's own constant value, since eden's `Timeouts`
convention (`git_setup`, `commit_collection`, ...) already favors exposing
"bound a step that could hang" knobs rather than hardcoding them. It lives
on the provider factory, not the orchestrator-level `Timeouts` dataclass,
because it only governs `SandboxProvider.create()` itself — a step
`Timeouts` doesn't currently reach into.

`check_image_uid`'s existence-and-UID-check pre-flight was consolidated into
a new `verify_image()` (`container_image.py`) so `container.py` threads one
`remaining()` call through both checks instead of two separate call sites.

## Consequences

- A hung `docker`/`podman` daemon now fails after `create_timeout` seconds
  (120s default) with a distinct `ContainerStartTimeout`, instead of hanging
  the calling thread indefinitely. Verified against a real Docker daemon:
  normal creation still succeeds, and an artificially tiny `create_timeout`
  reliably raises the new error.
- The mount-parent-prep step (`prepare_file_mount_parents`) now also takes
  an optional `remaining` callable, threaded the same way; other callers
  (there are none outside `container.py`) keep working untimed via the
  default `None`.
- `Timeouts` (the orchestrator-level dataclass) is unchanged — this is a
  provider-level knob, not a run-loop one.

## See also

- `eden/providers/_impl/container_deadline.py` — `container_start_deadline`.
- `eden/providers/_impl/container_image.py` — `verify_image`.
- [`docs/container-sandbox-providers.md`](../container-sandbox-providers.md) — `create_timeout` in the provider signatures.
- [`docs/sandbox-worktree-errors.md`](../sandbox-worktree-errors.md#containerstarttimeout) — `ContainerStartTimeout`.
