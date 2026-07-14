"""test_bind_mount: in-tree filesystem-backed bind-mount provider for tests.

The "sandbox" is a temp directory carved per-create() call. ``exec``
optionally runs a real ``/bin/sh -c`` subprocess, but can also be
short-circuited with a caller-supplied ``exec_handler`` so unit tests
don't need a real shell. Every call is appended to a public
:class:`CallLog` so tests can assert on the orchestrator's traffic.

The provider is intentionally similar to ``no_sandbox`` but:

* it allocates its own temp worktree under ``tempfile.gettempdir()``
  rather than mounting the host worktree, so tests don't have to set up
  a git worktree to exercise the provider abstraction;
* it records every ``exec`` / ``copy_file_in`` / ``copy_file_out`` /
  ``close`` call;
* it accepts an ``exec_handler`` callable for stubbed responses;
* on ``close()`` it removes the temp directory.

External provider authors can copy this file as a starting point, since
it shows the full bind-mount protocol surface without any third-party
dependency.
"""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from eden.providers._helpers import make_bind_mount_provider
from eden.providers._protocols import BindMountSandboxHandle, SandboxProvider
from eden.providers._types import CreateOptions, ExecResult
from eden.sandboxes._exec import stream_exec
from eden.sandboxes.test_bind_mount._log import CallLog, CopyCall, ExecCall

ExecHandler = Callable[[ExecCall], ExecResult]


@dataclass
class _TestBindMountHandle:
    worktree_path: Path
    _sandbox_root: Path
    _log: CallLog
    _exec_handler: ExecHandler | None

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
        call = ExecCall(
            cmd=cmd,
            cwd=cwd,
            env_keys=tuple(sorted(env.keys())) if env else (),
            timeout=timeout,
            stdin=stdin,
        )
        self._log.exec_calls.append(call)

        if self._exec_handler is not None:
            result = self._exec_handler(call)
            if on_line is not None:
                for line in result.stdout.splitlines():
                    on_line(line)
            return result

        return stream_exec(
            cmd,
            cmd_for_error=cmd,
            # ``shell=True`` lets the host's native shell (cmd.exe on
            # Windows, /bin/sh on POSIX) interpret ``cmd`` — keeps the
            # test provider runnable on every platform the rest of eden
            # supports rather than hard-coding ``/bin/sh``.
            shell=True,
            cwd=cwd if cwd is not None else self.worktree_path,
            env=env,
            on_line=on_line,
            timeout=timeout,
            stdin=stdin,
        )

    def copy_file_in(self, host: Path, sandbox: Path) -> None:
        self._log.copy_calls.append(CopyCall(direction="in", host=host, sandbox=sandbox))
        sandbox.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(host, sandbox)

    def copy_file_out(self, sandbox: Path, host: Path) -> None:
        self._log.copy_calls.append(CopyCall(direction="out", host=host, sandbox=sandbox))
        host.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(sandbox, host)

    def close(self) -> None:
        self._log.closed = True
        if self._sandbox_root.exists():
            shutil.rmtree(self._sandbox_root, ignore_errors=True)


def provider(
    *,
    exec_handler: ExecHandler | None = None,
    call_log: CallLog | None = None,
) -> SandboxProvider:
    """Filesystem-backed bind-mount provider for tests.

    Args:
        exec_handler: When given, short-circuits real subprocess execution —
            the handler receives the captured ``ExecCall`` and returns the
            ``ExecResult`` the test wants to inject.
        call_log: Optional ``CallLog`` shared between the test and the
            provider. A fresh log is created when omitted; access it via
            ``provider().call_log`` once the orchestrator has called
            ``create()`` (rare; usually tests pass their own log in).

    Returns:
        A SandboxProvider that carves a fresh tmpdir per ``create()`` call
        and tracks every call on ``call_log``.
    """
    fixed_handler = exec_handler
    log = call_log if call_log is not None else CallLog()

    def _create(_opts: CreateOptions) -> BindMountSandboxHandle:
        sandbox_root = Path(tempfile.mkdtemp(prefix="eden-test-bm-"))
        worktree = sandbox_root / "workspace"
        worktree.mkdir(parents=True, exist_ok=True)
        return _TestBindMountHandle(
            worktree_path=worktree,
            _sandbox_root=sandbox_root,
            _log=log,
            _exec_handler=fixed_handler,
        )

    p = make_bind_mount_provider(name="test-bind-mount", create=_create)
    # Stash the log on the provider so callers can retrieve it without
    # having to pre-allocate one. Public read-only access.
    p.call_log = log  # type: ignore[attr-defined]
    return p


__all__ = ["CallLog", "CopyCall", "ExecCall", "ExecHandler", "provider"]
