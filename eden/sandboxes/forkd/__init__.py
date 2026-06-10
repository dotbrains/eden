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
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, cast

from eden.providers._helpers import make_isolated_provider
from eden.providers._impl import patch_sync
from eden.providers._impl.dir_upload import upload_dir_via_tar as _upload_dir_via_tar
from eden.providers._protocols import IsolatedSandboxHandle, SandboxProvider
from eden.providers._types import CreateOptions, ExecResult, FinalizeResult
from eden.sandboxes.errors import ExecFailed, ProviderUnavailable

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
            _upload_tree(handle.exec, src=opts.worktree_path, dst=_SANDBOX_WORKDIR)
            handle.baseline = _snapshot_via_exec(handle.exec, root=_SANDBOX_WORKDIR)
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
        if host.is_dir():
            result = _upload_dir_via_tar(self.exec, host=host, sandbox=sandbox)
            if result.exit_code != 0:
                raise ExecFailed(
                    result=result,
                    argv_or_cmd=f"copy_file_in (dir) {host} -> {sandbox}",
                )
            return
        data = host.read_bytes()
        b64 = base64.b64encode(data).decode("ascii")
        result = self.exec(
            f"mkdir -p {sandbox.parent.as_posix()} && "
            f"echo {b64} | base64 -d > {sandbox.as_posix()}",
        )
        if result.exit_code != 0:
            raise ExecFailed(
                result=result,
                argv_or_cmd=f"copy_file_in {host} -> {sandbox}",
            )

    def copy_file_out(self, sandbox: Path, host: Path) -> None:
        result = self.exec(f"base64 {sandbox.as_posix()}")
        if result.exit_code != 0:
            raise ExecFailed(
                result=result,
                argv_or_cmd=f"copy_file_out {sandbox} -> {host}",
            )
        host.parent.mkdir(parents=True, exist_ok=True)
        host.write_bytes(base64.b64decode(result.stdout))

    def finalize(self, target: Path) -> FinalizeResult:
        try:
            after = _snapshot_via_exec(self.exec, root=self.worktree_path)
        except Exception:
            return FinalizeResult(applied=False, files_changed=(), patch_size_bytes=0)

        diff_result = patch_sync.diff(before=self.baseline, after=after)
        if not (diff_result.added or diff_result.changed or diff_result.removed):
            return FinalizeResult(applied=True, files_changed=(), patch_size_bytes=0)

        with tempfile.TemporaryDirectory() as tmp_root_str:
            tmp_root = Path(tmp_root_str)
            for rel in sorted(diff_result.added | diff_result.changed):
                self.copy_file_out(self.worktree_path / rel, tmp_root / rel)
            return patch_sync.apply(diff_result, src=tmp_root, dst=target)

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


def _upload_tree(
    exec_fn: Callable[..., ExecResult],
    *,
    src: Path,
    dst: Path,
) -> None:
    """Upload every file under `src` (host) to `dst` (sandbox), preserving structure."""
    for path in src.rglob("*"):
        if path.is_dir():
            continue
        rel = path.relative_to(src)
        if any(part in (".git", ".eden") for part in rel.parts):
            continue
        b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        target = dst / rel
        result = exec_fn(
            f"mkdir -p {target.parent.as_posix()} && echo {b64} | base64 -d > {target.as_posix()}",
        )
        if result.exit_code != 0:
            raise RuntimeError(f"upload of {rel} failed: {result.stderr}")


def _snapshot_via_exec(
    exec_fn: Callable[..., ExecResult],
    *,
    root: Path,
) -> dict[Path, str]:
    """Hash every file under `root` in the sandbox into the `dict[Path, hex]`
    shape produced by `patch_sync.snapshot()` locally.

    Uses ``-exec sha256sum {} +`` rather than ``... | xargs sha256sum``: GNU
    xargs runs the command once with no arguments when find finds nothing, which
    makes sha256sum hash empty stdin and emit ``<hash>  -`` — corrupting the
    parsed snapshot. ``-exec ... +`` skips the command entirely on no matches
    and is portable across GNU/BSD find.
    """
    result = exec_fn(
        f"cd {root.as_posix()} && "
        "find . -type f "
        "-not -path './.git/*' -not -path './.eden/*' "
        "-exec sha256sum {} + 2>/dev/null"
    )
    out: dict[Path, str] = {}
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        # `sha256sum` format: "<hex>  ./relative/path"
        try:
            hex_digest, rest = line.split(maxsplit=1)
        except ValueError:
            continue
        rel = rest.strip()
        if rel.startswith("./"):
            rel = rel[2:]
        out[Path(rel)] = hex_digest
    return out


__all__ = ["provider"]
