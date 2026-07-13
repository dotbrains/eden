"""forkd microVM sandbox provider: SDK-driven isolated/finalizing sandbox.

forkd (https://github.com/deeplethe/forkd) is a Firecracker-based microVM
"fork from warm parent" runtime for AI-agent workloads. This provider drives it
through forkd's E2B-compatible Python SDK (``from forkd import Sandbox``): each
Eden run spawns a child microVM from a warm snapshot, runs the agent inside it,
and patch-syncs the result back to the host worktree on ``finalize()``.

Requires the optional ``forkd`` dependency (``pip install eden-agent[forkd]``)
and a Linux host with KVM — forkd does not run on macOS or Windows. The SDK is
imported lazily inside ``create()`` so importing this module (and the rest of
Eden) stays cross-platform; ``ProviderUnavailable`` is raised at create() time,
not factory time, matching the daytona/vercel providers.

The SDK surface used here is the E2B-compatible subset documented by forkd:
``Sandbox(...)`` construction, ``sandbox.commands.run(cmd, ...)`` returning a
result with ``.stdout`` / ``.stderr`` / ``.exit_code``, and ``sandbox.kill()``
teardown. File transfer and the finalize snapshot reuse base64-over-exec
(mirroring daytona/vercel) so they depend only on ``commands.run`` — not on any
particular SDK filesystem API. Pass ``sandbox_factory=`` to take full control of
construction (custom controller URL, memory limits, live-branch snapshots, …).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import cast

from eden.providers._helpers import make_isolated_provider
from eden.providers._protocols import IsolatedSandboxHandle, SandboxProvider
from eden.providers._types import CreateOptions
from eden.sandboxes._remote_exec import (
    snapshot_via_exec,
    upload_tree_via_exec,
)
from eden.sandboxes.errors import ProviderUnavailable
from eden.sandboxes.forkd._handle import _ForkdHandle, _ForkdSandbox

_SANDBOX_WORKDIR = Path("/workspace")


def provider(
    *,
    snapshot: str | None = None,
    env: Mapping[str, str] | None = None,
    timeout: float = 60.0,
    sandbox_factory: Callable[[], object] | None = None,
) -> SandboxProvider:
    """forkd microVM isolated/finalizing sandbox provider (E2B-compatible SDK).

    `snapshot` is the warm-parent snapshot tag children fork from; passed to the
    SDK as ``Sandbox(template=snapshot)``. `env` is forwarded into every command
    the agent runs (merged with `CreateOptions.env` from the orchestrator).
    `timeout` is the default per-command timeout in seconds.

    `sandbox_factory`, when given, is called with no arguments to construct the
    SDK sandbox, bypassing the default ``Sandbox(template=...)`` path. Use it to
    point at a non-default controller, set memory limits, or fork from a live
    checkpoint — anything the forkd SDK exposes that this thin wrapper does not.

    Raises `ProviderUnavailable` at `create()` time (not factory time) when the
    optional ``forkd`` dependency is not importable, so the factory can be
    imported on hosts without forkd installed.
    """
    fixed_env: dict[str, str] = dict(env) if env else {}
    fixed_timeout = timeout
    fixed_snapshot = snapshot
    fixed_factory = sandbox_factory

    def _create(opts: CreateOptions) -> IsolatedSandboxHandle:
        if fixed_factory is not None:
            sandbox = cast("_ForkdSandbox", fixed_factory())
        else:
            sandbox = _make_sandbox(snapshot=fixed_snapshot)

        merged_env: dict[str, str] = {**fixed_env, **dict(opts.env)}
        handle = _ForkdHandle(
            sandbox=sandbox,
            worktree_path=_SANDBOX_WORKDIR,
            host_worktree_path=opts.worktree_path,
            env=merged_env,
            timeout=fixed_timeout,
        )
        try:
            upload_tree_via_exec(
                handle.exec,
                src=opts.worktree_path,
                dst=_SANDBOX_WORKDIR,
                quote_paths=True,
            )
            handle.baseline = snapshot_via_exec(
                handle.exec,
                root=_SANDBOX_WORKDIR,
                quote_root=True,
            )
        except Exception:
            handle.close()
            raise
        return handle

    return make_isolated_provider(name="forkd", create=_create)


def _make_sandbox(*, snapshot: str | None) -> _ForkdSandbox:
    try:
        from forkd import Sandbox  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ProviderUnavailable(
            provider="forkd",
            binary="forkd (pip install eden-agent[forkd])",
        ) from exc
    if snapshot is not None:
        return cast("_ForkdSandbox", Sandbox(template=snapshot))
    return cast("_ForkdSandbox", Sandbox())


__all__ = ["_ForkdHandle", "provider"]
