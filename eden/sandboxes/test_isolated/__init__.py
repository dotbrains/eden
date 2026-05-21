"""test_isolated: in-tree filesystem-backed isolated provider for tests.

The "sandbox" is a temp directory carved per-create() call, populated
by copying the orchestrator-supplied worktree at create time. ``exec``
runs ``/bin/sh -c`` inside the temp dir (or a stub handler if one is
supplied). ``finalize(target)`` replays the in-sandbox state onto the
target via :mod:`eden.providers._impl.patch_sync`, matching the
production ``isolated`` provider.

Useful for:

* Exercising the orchestrator's ``IsolatedSandboxHandle.finalize`` path
  in tests without needing Daytona / Vercel credentials.
* External provider authors who want a worked example of an isolated
  provider that fits in one file.
"""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from eden.providers._helpers import make_isolated_provider
from eden.providers._impl import patch_sync
from eden.providers._protocols import IsolatedSandboxHandle, SandboxProvider
from eden.providers._types import CreateOptions, ExecResult, FinalizeResult
from eden.sandboxes._exec import stream_exec
from eden.sandboxes.test_bind_mount import (
    CallLog,
    CopyCall,
    ExecCall,
    ExecHandler,
)


@dataclass(frozen=True)
class FinalizeCall:
    target: Path
    applied: bool
    files_changed_count: int


@dataclass
class _TestIsolatedHandle:
    worktree_path: Path
    host_worktree_path: Path
    baseline: dict[Path, str]
    _sandbox_root: Path
    _log: CallLog
    _exec_handler: ExecHandler | None
    _finalize_calls: list[FinalizeCall] = field(default_factory=list)

    def exec(
        self,
        cmd: str,
        *,
        on_line: Callable[[str], None] | None = None,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> ExecResult:
        call = ExecCall(
            cmd=cmd,
            cwd=cwd,
            env_keys=tuple(sorted(env.keys())) if env else (),
            timeout=timeout,
        )
        self._log.exec_calls.append(call)

        if self._exec_handler is not None:
            result = self._exec_handler(call)
            if on_line is not None:
                for line in result.stdout.splitlines():
                    on_line(line)
            return result

        return stream_exec(
            ["/bin/sh", "-c", cmd],
            cmd_for_error=cmd,
            shell=False,
            cwd=cwd if cwd is not None else self.worktree_path,
            env=env,
            on_line=on_line,
            timeout=timeout,
        )

    def copy_file_in(self, host: Path, sandbox: Path) -> None:
        self._log.copy_calls.append(CopyCall(direction="in", host=host, sandbox=sandbox))
        sandbox.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(host, sandbox)

    def copy_file_out(self, sandbox: Path, host: Path) -> None:
        self._log.copy_calls.append(CopyCall(direction="out", host=host, sandbox=sandbox))
        host.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(sandbox, host)

    def finalize(self, target: Path) -> FinalizeResult:
        after = patch_sync.snapshot(self.worktree_path)
        d = patch_sync.diff(before=self.baseline, after=after)
        result = patch_sync.apply(d, src=self.worktree_path, dst=target)
        self._finalize_calls.append(
            FinalizeCall(
                target=target,
                applied=result.applied,
                files_changed_count=len(result.files_changed),
            )
        )
        return result

    @property
    def finalize_calls(self) -> tuple[FinalizeCall, ...]:
        return tuple(self._finalize_calls)

    def close(self) -> None:
        self._log.closed = True
        if self._sandbox_root.exists():
            shutil.rmtree(self._sandbox_root, ignore_errors=True)


_IGNORED_TOP_LEVEL: tuple[str, ...] = (".git", ".eden")


def _clone(src: Path, dst: Path) -> None:
    """Mirror ``src`` to ``dst`` excluding ``.git`` / ``.eden``.

    Plain ``shutil.copytree`` — no APFS clonefile optimisation since
    test fixtures are small.
    """
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(*_IGNORED_TOP_LEVEL))


def provider(
    *,
    exec_handler: ExecHandler | None = None,
    call_log: CallLog | None = None,
) -> SandboxProvider:
    """Filesystem-backed isolated provider for tests.

    Args:
        exec_handler: When given, short-circuits real subprocess execution.
        call_log: Optional shared ``CallLog`` (same class as
            ``test_bind_mount``).

    Returns:
        A SandboxProvider with ``kind="isolated"`` whose handle implements
        the full ``IsolatedSandboxHandle`` Protocol — including
        ``finalize(target)`` powered by ``patch_sync``.
    """
    fixed_handler = exec_handler
    log = call_log if call_log is not None else CallLog()

    def _create(opts: CreateOptions) -> IsolatedSandboxHandle:
        sandbox_root = Path(tempfile.mkdtemp(prefix="eden-test-iso-"))
        worktree = sandbox_root / "workspace"
        _clone(opts.worktree_path, worktree)
        baseline = patch_sync.snapshot(worktree)
        return _TestIsolatedHandle(
            worktree_path=worktree,
            host_worktree_path=opts.worktree_path,
            baseline=baseline,
            _sandbox_root=sandbox_root,
            _log=log,
            _exec_handler=fixed_handler,
        )

    p = make_isolated_provider(name="test-isolated", create=_create)
    p.call_log = log  # type: ignore[attr-defined]
    return p


__all__ = ["FinalizeCall", "provider"]
