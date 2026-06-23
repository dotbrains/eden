"""Recovery messages for finalize / sync-out failures.

When the post-iteration finalize step fails (an exception in
``handle.finalize(target)`` or ``FinalizeResult.applied=False``), the
orchestrator emits a copy-pastable hint that points the user at the
isolated worktree and the host target, with an ``rsync`` command to
complete the merge manually.

Eden's equivalent of the ``failedStep`` distinction (commits / diff /
untracked) is the snapshot / diff / apply model, so the per-step
branching collapses into a single shape with the failure description
carried inline.

The local isolated provider preserves its temp worktree on failure (via
``handle.preserve()``) so the rsync command actually points at a path
that still exists.
"""

from __future__ import annotations

import shlex
from pathlib import Path


def format_finalize_recovery(
    *,
    isolated_path: Path,
    target_path: Path,
    error: BaseException | None = None,
    files_failed: tuple[Path, ...] | None = None,
    preserved: bool = True,
) -> str:
    """Build a copy-pastable recovery message for a failed finalize.

    ``error`` and ``files_failed`` describe the two failure modes:

    * **Hard failure** — ``handle.finalize()`` raised. Pass the exception
      as ``error`` and leave ``files_failed=None``.
    * **Soft failure** — ``FinalizeResult.applied=False``. Pass the
      per-file failure list as ``files_failed`` (or ``()`` if unknown);
      ``error`` stays ``None``.

    ``preserved`` toggles the recovery commands. When ``True`` (default),
    the message includes an ``rsync`` line and a ``rm -rf`` cleanup; when
    ``False``, only the diagnostic header is emitted, because the
    isolated worktree was cleaned and the rsync command would point at a
    missing path.
    """
    iso_q = shlex.quote(str(isolated_path))
    tgt_q = shlex.quote(str(target_path))
    lines: list[str] = ["[eden] finalize failed — recovery info:"]
    if error is not None:
        lines.append(f"  error:    {error}")
    lines.append(f"  isolated: {isolated_path}")
    lines.append(f"  target:   {target_path}")
    if files_failed:
        lines.append("  files:")
        for f in files_failed:
            lines.append(f"    - {f}")
    if not preserved:
        return "\n".join(lines)
    lines.append("")
    lines.append("Recovery — merge isolated → target manually:")
    lines.append(f"  rsync -a --exclude=.git --exclude=.eden {iso_q}/ {tgt_q}/")
    lines.append("")
    lines.append("Then remove the isolated worktree:")
    lines.append(f"  rm -rf {iso_q}")
    return "\n".join(lines)


__all__ = ["format_finalize_recovery"]
