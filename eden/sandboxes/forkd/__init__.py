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

import base64
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, cast

from eden.providers._helpers import make_isolated_provider
from eden.providers._protocols import IsolatedSandboxHandle, SandboxProvider
from eden.providers._types import CreateOptions, ExecResult, FinalizeResult
from eden.sandboxes._remote_exec import (
    copy_file_in_via_exec,
    copy_file_out_via_exec,
    finalize_from_remote_snapshot,
    snapshot_via_exec,
    upload_tree_via_exec,
)
from eden.sandboxes.errors import ProviderUnavailable

_SANDBOX_WORKDIR = Path("/workspace")


class _ForkdCommandResult(Protocol):
    """The E2B-compatible result returned by ``commands.run``."""

    stdout: str
    stderr: str
    exit_code: int


class _ForkdCommands(Protocol):
    def run(
        self,
        cmd: str,
        *,
        cwd: str | None = ...,
        envs: Mapping[str, str] | None = ...,
        timeout: float | None = ...,
    ) -> _ForkdCommandResult: ...


class _ForkdSandbox(Protocol):
    """Structural type for the forkd SDK ``Sandbox`` object we drive."""

    commands: _ForkdCommands

    def kill(self) -> None: ...


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


@dataclass
class _ForkdHandle:
    sandbox: _ForkdSandbox
    worktree_path: Path
    host_worktree_path: Path
    env: dict[str, str]
    timeout: float
    baseline: dict[Path, str] = field(default_factory=dict)

    def exec(
        self,
        cmd: str,
        *,
        on_line: Callable[[str], None] | None = None,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
        stdin: str | None = None,
    ) -> ExecResult:
        # The SDK has no stdin channel; encode the payload as base64 and let the
        # in-guest shell decode and pipe it, mirroring the cloud REST providers.
        # This survives the SDK boundary without quoting issues and delivers
        # payloads larger than the 128 KB execve argv limit.
        if stdin is not None:
            b64 = base64.b64encode(stdin.encode("utf-8")).decode("ascii")
            cmd = f"printf '%s' {b64} | base64 -d | ({cmd})"

        merged_env = {**self.env, **(dict(env) if env else {})}
        kwargs: dict[str, object] = {}
        if cwd is not None:
            kwargs["cwd"] = cwd.as_posix()
        if merged_env:
            kwargs["envs"] = merged_env
        effective_timeout = timeout if timeout is not None else self.timeout
        if effective_timeout is not None:
            kwargs["timeout"] = effective_timeout

        try:
            result = self.sandbox.commands.run(cmd, **kwargs)  # type: ignore[arg-type]
        except Exception as exc:
            return _exc_to_exec_result(exc)
        out = _result_to_exec_result(result)
        if on_line is not None:
            for line in out.stdout.splitlines():
                on_line(line)
        return out

    def copy_file_in(self, host: Path, sandbox: Path) -> None:
        copy_file_in_via_exec(self.exec, host=host, sandbox=sandbox, quote_paths=True)

    def copy_file_out(self, sandbox: Path, host: Path) -> None:
        copy_file_out_via_exec(self.exec, sandbox=sandbox, host=host, quote_paths=True)

    def finalize(self, target: Path) -> FinalizeResult:
        return finalize_from_remote_snapshot(
            snapshot=lambda: snapshot_via_exec(self.exec, root=self.worktree_path, quote_root=True),
            copy_file_out=self.copy_file_out,
            baseline=self.baseline,
            worktree_path=self.worktree_path,
            target=target,
        )

    def close(self) -> None:
        # Called from a finally block; never raise on teardown (matches the
        # docker/podman/cloud providers' idempotent close).
        try:
            self.sandbox.kill()
        except Exception:
            pass


def _result_to_exec_result(result: _ForkdCommandResult) -> ExecResult:
    return ExecResult(
        stdout=str(result.stdout or ""),
        stderr=str(result.stderr or ""),
        exit_code=int(result.exit_code or 0),
    )


def _exc_to_exec_result(exc: Exception) -> ExecResult:
    # E2B-compatible SDKs raise on non-zero exit (CommandExitException) and carry
    # the real exit_code/stdout/stderr on the exception. Recover them when
    # present; otherwise treat it as a transport failure (exit_code -1).
    code = getattr(exc, "exit_code", None)
    if isinstance(code, int):
        return ExecResult(
            stdout=str(getattr(exc, "stdout", "") or ""),
            stderr=str(getattr(exc, "stderr", "") or str(exc)),
            exit_code=code,
        )
    return ExecResult(stdout="", stderr=str(exc), exit_code=-1)


__all__ = ["provider"]
