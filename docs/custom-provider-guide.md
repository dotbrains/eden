# Custom provider guide

Implementation notes for out-of-tree sandbox providers. Start with
[Custom providers](custom-providers.md) for the Protocol reference and factory helper signatures.

---

## Skeleton: a custom isolated provider

A minimum viable cloud-style provider. Replace the bodies with REST calls or whatever transport you target. Type-checks against the actual Protocols.

```python
"""my_provider: example custom isolated sandbox."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from eden import (
    CreateOptions,
    ExecResult,
    FinalizeResult,
    IsolatedSandboxHandle,
    SandboxProvider,
    make_isolated_provider,
)


@dataclass
class _MyHandle:
    worktree_path: Path  # sandbox-side path
    host_worktree_path: Path  # host worktree the orchestrator carved

    def exec(
        self,
        cmd: str,
        *,
        on_line: Callable[[str], None] | None = None,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> ExecResult:
        # Run `cmd` in the sandbox. Stream stdout via on_line(line).
        # Return an ExecResult populated with stdout, stderr, exit_code.
        raise NotImplementedError

    def copy_file_in(self, host: Path, sandbox: Path) -> None:
        # Push `host` (host path) to `sandbox` (sandbox path).
        raise NotImplementedError

    def copy_file_out(self, sandbox: Path, host: Path) -> None:
        # Pull `sandbox` (sandbox path) to `host` (host path).
        raise NotImplementedError

    def finalize(self, target: Path) -> FinalizeResult:
        # Replay sandbox-side changes onto `target` (host worktree path).
        # Return what was applied; orchestrator logs the result.
        return FinalizeResult(applied=True, files_changed=(), patch_size_bytes=0)

    def close(self) -> None:
        # Release resources. Called in a finally block; do not raise.
        return None


def provider(*, endpoint: str = "https://example.invalid") -> SandboxProvider:
    fixed_endpoint = endpoint

    def _create(opts: CreateOptions) -> IsolatedSandboxHandle:
        # 1. Provision the sandbox via your transport (REST, gRPC, SSH...).
        # 2. Upload opts.worktree_path contents into the sandbox.
        # 3. Snapshot the baseline so finalize() can diff against it.
        sandbox_workdir = Path("/workspace")
        return _MyHandle(
            worktree_path=sandbox_workdir,
            host_worktree_path=opts.worktree_path,
        )

    return make_isolated_provider(name="my-provider", create=_create)


__all__ = ["provider"]
```

Plug it into `run()`:

```python
from eden import run, simulated_agent
from my_pkg.eden_provider import provider as my_provider

result = run(
    agent=simulated_agent(output="<promise>COMPLETE</promise>\n"),
    sandbox=my_provider(endpoint="https://my-runtime.example.com"),
    prompt="echo hello",
    max_iterations=1,
)
```

## Worked examples in-tree

Read these for full implementations of each shape:

- **Bind-mount, host-side** — `eden/sandboxes/no_sandbox/__init__.py`. ~60 LoC.
- **Bind-mount, container** — `eden/sandboxes/docker/__init__.py` and `eden/providers/_impl/container.py`. Delegates to a shared container helper.
- **Patch-sync, local** — `eden/sandboxes/isolated/__init__.py`. Copy-tree, snapshot, run, diff, apply.
- **REST cloud, isolated** — `eden/sandboxes/daytona/__init__.py`. Provisions a remote sandbox over REST, snapshots via `find -exec sha256sum`, pulls changed files in `finalize()`, and reuses `eden.providers._impl.patch_sync` for the apply step.
- **Test providers** — `eden/sandboxes/test_bind_mount/__init__.py` and `eden/sandboxes/test_isolated/__init__.py`. Filesystem-only providers that carve a tmpdir per `create()` call. Both expose a `CallLog` so tests can assert on the orchestrator's traffic, and accept an `exec_handler` callable to stub responses without spawning real subprocesses. Use them as a copy-paste starting point for your own provider.

```python
from eden import run, simulated_agent
from eden.sandboxes.test_bind_mount import CallLog, provider as test_bind_mount

log = CallLog()
result = run(
    sandbox=test_bind_mount(call_log=log),
    agent=simulated_agent(output="<promise>COMPLETE</promise>\n"),
    prompt="ignored",
    max_iterations=1,
)
assert log.closed is True
```

## Conventions worth following

- **Idempotent close** — `close()` is called from a `finally` block. Catch transport exceptions; never raise from `close()`.
- **Lazy credential checks** — raise `ProviderUnavailable` from `create()`, not from your `provider(...)` factory. This lets users import the factory without credentials in scope (matches `daytona`, `vercel`).
- **No `.git` / `.eden` upload** — the in-tree providers exclude these paths from the snapshot; do the same to keep finalize diffs small and avoid leaking session state into the sandbox.
- **Reuse `patch_sync`** — `eden.providers._impl.patch_sync` exposes `snapshot()`, `diff()`, and `apply()` so isolated providers do not have to reimplement the diff logic. `daytona` and `isolated` both use it.

## See also

- [Custom providers](custom-providers.md) — Protocol reference and factory helper signatures.
- [Sandbox providers](sandbox-providers.md) — the in-tree provider catalog and matrix.
- [Errors](errors.md) — provider error hierarchy and failure handling.
