"""no_sandbox: run commands directly on the host via subprocess+shell."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from eden.abort import AbortSignal
from eden.providers._helpers import make_bind_mount_provider
from eden.providers._protocols import (
    BindMountSandboxHandle,
    SandboxProvider,
)
from eden.providers._types import CreateOptions, ExecResult
from eden.sandboxes._exec import stream_exec
from eden.streaming._bounded_tail import DEFAULT_MAX_CHARS


def _wait_interactive_process(proc: subprocess.Popen[bytes], signal: AbortSignal | None) -> int:
    while True:
        if signal is not None and signal.is_aborted():
            proc.terminate()
            try:
                proc.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            signal.raise_if_aborted()
        try:
            return proc.wait(timeout=0.1)
        except subprocess.TimeoutExpired:
            time.sleep(0)


@dataclass
class _NoSandboxHandle:
    worktree_path: Path
    max_output_tail_chars: int
    base_env: Mapping[str, str]

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
        return stream_exec(
            cmd,
            cmd_for_error=cmd,
            shell=True,
            cwd=cwd or self.worktree_path,
            env={**dict(self.base_env), **dict(env or {})},
            on_line=on_line,
            timeout=timeout,
            stdin=stdin,
            max_output_tail_chars=self.max_output_tail_chars,
        )

    def copy_file_in(self, host: Path, sandbox: Path) -> None:
        shutil.copy2(host, sandbox)

    def copy_file_out(self, sandbox: Path, host: Path) -> None:
        shutil.copy2(sandbox, host)

    def interactive_exec(
        self,
        argv: list[str],
        *,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        signal: AbortSignal | None = None,
    ) -> int:
        """Run ``argv`` natively with stdio inherited; return the exit code.

        ``cwd`` defaults to the handle's worktree path. ``env`` is merged onto
        ``os.environ``; the parent's TTY is preserved (no pipes).
        """
        if signal is not None:
            signal.raise_if_aborted()
        merged_env = {**os.environ, **(env or {})}
        proc = subprocess.Popen(
            argv,
            cwd=str(cwd) if cwd is not None else str(self.worktree_path),
            env=merged_env,
            shell=sys.platform == "win32",
        )
        return _wait_interactive_process(proc, signal)

    def close(self) -> None:
        return None


def _make_create_no_sandbox(
    *, max_output_tail_chars: int, provider_env: Mapping[str, str]
) -> Callable[[CreateOptions], BindMountSandboxHandle]:
    def _create_no_sandbox(opts: CreateOptions) -> BindMountSandboxHandle:
        return _NoSandboxHandle(
            worktree_path=opts.worktree_path,
            max_output_tail_chars=max_output_tail_chars,
            base_env={**dict(provider_env), **dict(opts.env)},
        )

    return _create_no_sandbox


def provider(
    *,
    env: Mapping[str, str] | None = None,
    max_output_tail_chars: int = DEFAULT_MAX_CHARS,
) -> SandboxProvider:
    return make_bind_mount_provider(
        name="no_sandbox",
        create=_make_create_no_sandbox(
            max_output_tail_chars=max_output_tail_chars,
            provider_env=dict(env or {}),
        ),
        supported_strategies=frozenset({"head", "merge_to_head", "named"}),
    )


__all__ = ["provider"]
