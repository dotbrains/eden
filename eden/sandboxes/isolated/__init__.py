"""Local isolated provider: copy worktree, run agent in copy, patch-sync back."""

from __future__ import annotations

import re
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

from eden.errors import CopyToWorktreeError
from eden.providers._helpers import make_isolated_provider
from eden.providers._impl import patch_sync
from eden.providers._protocols import IsolatedSandboxHandle, SandboxProvider
from eden.providers._types import CreateOptions
from eden.sandboxes.isolated._handle import IsolatedHandle

_IGNORED_TOP_LEVEL: tuple[str, ...] = (".git", ".eden")
_DEFAULT_COPY_TIMEOUT_SECONDS: float = 60.0


def _clone_tree(src: Path, dst: Path, *, timeout: float | None) -> None:
    """Copy ``src`` to ``dst`` (must not exist), excluding ``.git`` / ``.eden``.

    Uses ``cp -cR`` (APFS clonefile) on macOS so cloning a large worktree is
    near-instant on APFS-backed volumes. Falls back to ``shutil.copytree`` on
    non-Darwin or when ``cp`` fails for any reason. Raises
    ``CopyToWorktreeError`` (with ``timed_out=True``) if the copy doesn't
    complete within ``timeout`` seconds; ``timeout=None`` disables the budget.
    """
    if sys.platform == "darwin":
        try:
            subprocess.run(
                ["cp", "-cR", str(src), str(dst)],
                check=True,
                capture_output=True,
                timeout=timeout,
            )
            for ignored in _IGNORED_TOP_LEVEL:
                victim = dst / ignored
                if victim.exists():
                    shutil.rmtree(victim, ignore_errors=True)
            return
        except subprocess.TimeoutExpired as exc:
            if dst.exists():
                shutil.rmtree(dst, ignore_errors=True)
            raise CopyToWorktreeError(
                code="copy.to_worktree_timeout",
                message=(f"copying worktree {src} → {dst} did not complete within {timeout}s"),
                hint=(
                    "increase Timeouts.copy_to_worktree or shrink the worktree "
                    "(check for accidentally-tracked build artefacts)"
                ),
                cause=exc,
                source=src,
                target=dst,
                timeout=timeout,
                timed_out=True,
            ) from exc
        except subprocess.CalledProcessError:
            # Partial dst may exist — wipe before falling back so copytree's
            # "destination must not exist" precondition holds.
            if dst.exists():
                shutil.rmtree(dst, ignore_errors=True)
        except FileNotFoundError:
            # ``cp`` not on PATH (extremely unlikely on macOS) — fall through.
            pass
    try:
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns(*_IGNORED_TOP_LEVEL))
    except OSError as exc:
        if dst.exists():
            shutil.rmtree(dst, ignore_errors=True)
        raise CopyToWorktreeError(
            message=f"copying worktree {src} → {dst} failed: {exc}",
            hint="check disk space, permissions, and that ``src`` is readable",
            cause=exc,
            source=src,
            target=dst,
            timeout=timeout,
        ) from exc


_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _sanitize_seed(s: str) -> str:
    out = _NAME_RE.sub("-", s).strip("-")
    if not out:
        return "run"
    return out[:64] if len(out) > 64 else out


def provider(
    *,
    base_dir: Path | None = None,
    copy_timeout: float | None = _DEFAULT_COPY_TIMEOUT_SECONDS,
) -> SandboxProvider:
    """Local isolated provider: copy worktree to a tmp dir, run agent there,
    finalize by patch-syncing changes back to the host worktree.

    ``base_dir`` defaults to ``<host_repo_path>/.eden/isolated/`` (sibling of
    ``.eden/worktrees/`` and ``.eden/sessions/``). Each ``create()`` call
    carves a fresh subdirectory there.

    ``copy_timeout`` bounds the worktree clone (``cp -cR`` on macOS,
    ``shutil.copytree`` elsewhere). On exceedance the partial copy is wiped
    and a ``CopyToWorktreeError`` with ``timed_out=True`` is raised. Set
    ``None`` to disable the budget (large monorepos on slow disks).
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
        _clone_tree(opts.worktree_path, isolated_root, timeout=copy_timeout)

        return IsolatedHandle(
            worktree_path=isolated_root,
            host_worktree_path=opts.worktree_path,
            baseline=baseline,
        )

    return make_isolated_provider(name="isolated", create=_create)


__all__ = ["provider"]
