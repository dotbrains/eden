"""Local isolated provider: copy worktree, run agent in copy, patch-sync back."""

from __future__ import annotations

import re
import secrets
import shutil
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from eden.providers._helpers import make_isolated_provider
from eden.providers._impl import patch_sync
from eden.providers._protocols import IsolatedSandboxHandle, SandboxProvider
from eden.providers._types import CreateOptions, ExecResult, FinalizeResult
from eden.sandboxes._exec import stream_exec

_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _sanitize_seed(s: str) -> str:
    out = _NAME_RE.sub("-", s).strip("-")
    if not out:
        return "run"
    return out[:64] if len(out) > 64 else out


@dataclass
class _IsolatedHandle:
    worktree_path: Path
    host_worktree_path: Path
    baseline: dict[Path, str]

    def exec(
        self,
        cmd: str,
        *,
        on_line: Callable[[str], None] | None = None,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> ExecResult:
        merged_cwd = cwd if cwd is not None else self.worktree_path
        return stream_exec(
            ["/bin/sh", "-c", cmd],
            cmd_for_error=cmd,
            shell=False,
            cwd=merged_cwd,
            env=env,
            on_line=on_line,
            timeout=timeout,
        )

    def copy_file_in(self, host: Path, sandbox: Path) -> None:
        sandbox.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(host, sandbox)

    def copy_file_out(self, sandbox: Path, host: Path) -> None:
        host.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(sandbox, host)

    def finalize(self, target: Path) -> FinalizeResult:
        after = patch_sync.snapshot(self.worktree_path)
        d = patch_sync.diff(before=self.baseline, after=after)
        return patch_sync.apply(d, src=self.worktree_path, dst=target)

    def close(self) -> None:
        if self.worktree_path.exists():
            shutil.rmtree(self.worktree_path, ignore_errors=True)


def provider(*, base_dir: Path | None = None) -> SandboxProvider:
    """Local isolated provider: copy worktree to a tmp dir, run agent there,
    finalize by patch-syncing changes back to the host worktree.

    ``base_dir`` defaults to ``<host_repo_path>/.eden/isolated/`` (sibling of
    ``.eden/worktrees/`` and ``.eden/sessions/``). Each ``create()`` call
    carves a fresh subdirectory there.
    """
    fixed_base = base_dir

    def _create(opts: CreateOptions) -> IsolatedSandboxHandle:
        base = (
            fixed_base if fixed_base is not None else (opts.host_repo_path / ".eden" / "isolated")
        )
        base.mkdir(parents=True, exist_ok=True)
        suffix = secrets.token_hex(4)
        seed = opts.name_hint or opts.branch
        isolated_root = base / f"{_sanitize_seed(seed)}-{suffix}"

        baseline = patch_sync.snapshot(opts.worktree_path)
        shutil.copytree(
            opts.worktree_path,
            isolated_root,
            ignore=shutil.ignore_patterns(".git", ".eden"),
        )

        return _IsolatedHandle(
            worktree_path=isolated_root,
            host_worktree_path=opts.worktree_path,
            baseline=baseline,
        )

    return make_isolated_provider(name="isolated", create=_create)


__all__ = ["provider"]
