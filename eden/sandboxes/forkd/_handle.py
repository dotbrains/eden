"""forkd sandbox handle and SDK protocol types."""

from __future__ import annotations

import base64
import shlex
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from eden.providers._types import ExecResult, FinalizeResult
from eden.sandboxes._remote_exec import (
    copy_file_in_via_exec,
    copy_file_out_via_exec,
    finalize_from_remote_snapshot,
    snapshot_via_exec,
)


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
        if cwd is not None:
            cmd = f"cd {shlex.quote(cwd.as_posix())} && ({cmd})"
        kwargs: dict[str, object] = {}
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


__all__ = ["_ForkdHandle", "_ForkdSandbox"]
