# Custom Provider Skeleton

Minimum viable cloud-style provider skeleton for out-of-tree sandbox providers.
Replace the bodies with REST calls or whatever transport you target. The example
type-checks against Eden's public Protocols.

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

## Plug it into `run()`

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

## See also

- [Custom provider guide](custom-provider-guide.md) - examples and conventions.
- [Custom providers](custom-providers.md) - Protocol reference and factory helpers.
